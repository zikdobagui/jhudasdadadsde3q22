#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de Backup Automático
"""

import os
import json
import zipfile
import shutil
from datetime import datetime
import threading
import time

class BackupManager:
    def __init__(self):
        self.backup_dir = 'backups'
        self.config_file = 'backup_config.json'
        self.is_running = False
        self.backup_thread = None
        
        # Criar diretório de backups se não existir
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        # Carregar configuração
        self.config = self.load_config()
    
    def load_config(self):
        """Carrega configuração de backup"""
        default_config = {
            'auto_backup_enabled': False,
            'backup_interval_hours': 6,
            'max_backups': 10,
            'last_backup': None
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return default_config
        return default_config
    
    def save_config(self):
        """Salva configuração de backup"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"[BACKUP] Erro ao salvar config: {e}")
            return False
    
    def create_backup(self):
        """Cria um backup completo"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Criar arquivo zip
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Backup do database
                if os.path.exists('database'):
                    for root, dirs, files in os.walk('database'):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, '.')
                            zipf.write(file_path, arcname)
                
                # Backup de settings
                if os.path.exists('settings'):
                    for root, dirs, files in os.walk('settings'):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, '.')
                            zipf.write(file_path, arcname)
                
                # Backup de logs importantes
                if os.path.exists('log'):
                    for root, dirs, files in os.walk('log'):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, '.')
                            zipf.write(file_path, arcname)
                
                # Backup de arquivos importantes na raiz
                important_files = [
                    'pessoas.json',
                    'backup_config.json'
                ]
                for file in important_files:
                    if os.path.exists(file):
                        zipf.write(file)
            
            # Atualizar config
            self.config['last_backup'] = datetime.now().isoformat()
            self.save_config()
            
            # Limpar backups antigos
            self.cleanup_old_backups()
            
            return backup_path
        
        except Exception as e:
            print(f"[BACKUP] Erro ao criar backup: {e}")
            return None
    
    def cleanup_old_backups(self):
        """Remove backups antigos mantendo apenas os mais recentes"""
        try:
            backups = []
            for file in os.listdir(self.backup_dir):
                if file.startswith('backup_') and file.endswith('.zip'):
                    file_path = os.path.join(self.backup_dir, file)
                    backups.append((file_path, os.path.getmtime(file_path)))
            
            # Ordenar por data (mais recente primeiro)
            backups.sort(key=lambda x: x[1], reverse=True)
            
            # Remover backups excedentes
            max_backups = self.config.get('max_backups', 10)
            for backup_path, _ in backups[max_backups:]:
                try:
                    os.remove(backup_path)
                    print(f"[BACKUP] Backup antigo removido: {os.path.basename(backup_path)}")
                except Exception as e:
                    print(f"[BACKUP] Erro ao remover backup: {e}")
        
        except Exception as e:
            print(f"[BACKUP] Erro ao limpar backups: {e}")
    
    def list_backups(self):
        """Lista todos os backups disponíveis"""
        try:
            backups = []
            for file in os.listdir(self.backup_dir):
                if file.startswith('backup_') and file.endswith('.zip'):
                    file_path = os.path.join(self.backup_dir, file)
                    size = os.path.getsize(file_path)
                    mtime = os.path.getmtime(file_path)
                    backups.append({
                        'name': file,
                        'path': file_path,
                        'size': size,
                        'date': datetime.fromtimestamp(mtime)
                    })
            
            # Ordenar por data (mais recente primeiro)
            backups.sort(key=lambda x: x['date'], reverse=True)
            return backups
        
        except Exception as e:
            print(f"[BACKUP] Erro ao listar backups: {e}")
            return []
    
    def enable_auto_backup(self, interval_hours=6):
        """Ativa backup automático"""
        self.config['auto_backup_enabled'] = True
        self.config['backup_interval_hours'] = interval_hours
        self.save_config()
        
        if not self.is_running:
            self.start_auto_backup()
        
        return True
    
    def disable_auto_backup(self):
        """Desativa backup automático"""
        self.config['auto_backup_enabled'] = False
        self.save_config()
        self.stop_auto_backup()
        return True
    
    def start_auto_backup(self):
        """Inicia thread de backup automático"""
        if self.is_running:
            return
        
        self.is_running = True
        self.backup_thread = threading.Thread(target=self._auto_backup_loop, daemon=True)
        self.backup_thread.start()
        print("[BACKUP] Sistema de backup automático iniciado")
    
    def stop_auto_backup(self):
        """Para thread de backup automático"""
        self.is_running = False
        print("[BACKUP] Sistema de backup automático parado")
    
    def _auto_backup_loop(self):
        """Loop de backup automático"""
        while self.is_running:
            if self.config.get('auto_backup_enabled', False):
                interval_hours = self.config.get('backup_interval_hours', 6)
                interval_seconds = interval_hours * 3600
                
                # Aguardar intervalo
                time.sleep(interval_seconds)
                
                # Criar backup
                if self.is_running and self.config.get('auto_backup_enabled', False):
                    print(f"[BACKUP] Criando backup automático...")
                    backup_path = self.create_backup()
                    if backup_path:
                        print(f"[BACKUP] Backup automático criado: {os.path.basename(backup_path)}")
            else:
                time.sleep(60)  # Verificar a cada minuto se foi reativado
    
    def get_status(self):
        """Retorna status do sistema de backup"""
        backups = self.list_backups()
        return {
            'auto_backup_enabled': self.config.get('auto_backup_enabled', False),
            'backup_interval_hours': self.config.get('backup_interval_hours', 6),
            'max_backups': self.config.get('max_backups', 10),
            'last_backup': self.config.get('last_backup'),
            'total_backups': len(backups),
            'backups': backups
        }

# Instância global
backup_manager = BackupManager()
