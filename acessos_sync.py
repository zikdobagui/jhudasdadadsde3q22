import json
import hashlib
import time
import requests
import threading
import os
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuração de logging com rotação para evitar arquivos muito grandes
log_handler = RotatingFileHandler(
    'sync_log.txt', 
    maxBytes=5*1024*1024,  # 5MB máximo
    backupCount=3,  # Manter 3 backups
    encoding='utf-8'
)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[log_handler]
)

class RamonSyncManager:
    def __init__(self, server_url="http://135.148.144.90:5005", api_key="bot_sync_2024"):
        self.server_url = server_url
        self.api_key = api_key
        self.acessos_file = "database/acessos.json"
        self.hash_file = "database/.sync_hash"
        self.sync_interval = 30  # segundos
        self.is_running = False
        self.sync_thread = None
        self.max_retries = 3
        self.retry_delay = 5  # segundos base para backoff
        
        # Configurar sessão HTTP com retry robusto
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
            backoff_factor=1,
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def calculate_file_hash(self):
        """Calcula hash MD5 do arquivo acessos.json"""
        try:
            with open(self.acessos_file, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except FileNotFoundError:
            return None
        except Exception as e:
            logging.error(f"Erro ao calcular hash: {e}")
            return None
    
    def get_stored_hash(self):
        """Recupera o hash armazenado anteriormente"""
        try:
            with open(self.hash_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
        except Exception:
            return None
    
    def store_hash(self, hash_value):
        """Armazena o hash atual"""
        try:
            os.makedirs(os.path.dirname(self.hash_file), exist_ok=True)
            with open(self.hash_file, 'w') as f:
                f.write(hash_value)
        except Exception as e:
            logging.error(f"Erro ao armazenar hash: {e}")
    
    def load_acessos_data(self):
        """Carrega dados do arquivo acessos.json"""
        try:
            with open(self.acessos_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Erro ao carregar acessos.json: {e}")
            return None
    
    def filter_sensitive_data(self, data):
        """Filtra dados sensíveis antes de enviar para o servidor"""
        if not data or 'acessos' not in data:
            return data
        
        # Palavras-chave que indicam dados sensíveis (incluindo as do Ramon)
        sensitive_keywords = [
            'SUPORTE',
            'CHAME NO SUPORTE',
            'MANDA O GMAIL NOVO PRO SUPORTE',
            'MANDE O EMAIL PRO SUPORTE',
            'PEDE AO SUPORTE',
            'ENTREGA EM ATE 12hr',
            'TEENVIAREIUMCODIGOPORLA',
            'suporte',
            'teenviareiumcodigoporla',
            'VOCE FURARÁ A FILA',
            'ASSIM QUE VER SUA MENSAGEM',
            'COM SEU NÚMERO',
            'EMAIL',
            'SENHA'
        ]
        
        filtered_acessos = []
        filtered_count = 0
        
        for acesso in data['acessos']:
            email = acesso.get('email', '').upper()
            senha = acesso.get('senha', '').upper()
            descricao = acesso.get('descricao', '').upper()
            nome = acesso.get('nome', '').upper()
            
            # Verifica se contém palavras sensíveis em qualquer campo
            is_sensitive = False
            matched_keyword = None
            matched_field = None
            
            for keyword in sensitive_keywords:
                keyword_upper = keyword.upper()
                if keyword_upper in email:
                    is_sensitive = True
                    matched_keyword = keyword
                    matched_field = "email"
                    break
                elif keyword_upper in senha:
                    is_sensitive = True
                    matched_keyword = keyword
                    matched_field = "senha"
                    break
                elif keyword_upper in descricao:
                    is_sensitive = True
                    matched_keyword = keyword
                    matched_field = "descricao"
                    break
                elif keyword_upper in nome:
                    is_sensitive = True
                    matched_keyword = keyword
                    matched_field = "nome"
                    break
            
            if is_sensitive:
                filtered_count += 1
                # Log detalhado do que foi filtrado
                logging.info(f"[RAMON] Filtrado: '{acesso.get('nome', 'N/A')}' - Palavra '{matched_keyword}' encontrada no campo '{matched_field}'")
            
            # Só adiciona se não for sensível
            if not is_sensitive:
                filtered_acessos.append(acesso)
        
        # Cria nova estrutura com dados filtrados
        filtered_data = {
            'acessos': filtered_acessos
        }
        
        # Log apenas no arquivo, não no console
        if filtered_count > 0:
            logging.info(f"[RAMON] Filtrados {filtered_count} acessos sensíveis (não enviados ao servidor)")
        
        return filtered_data
    
    def sync_to_server(self, force=False):
        """Sincroniza dados com o servidor com retry robusto"""
        for attempt in range(self.max_retries):
            try:
                current_hash = self.calculate_file_hash()
                if not current_hash:
                    logging.warning("[RAMON] Não foi possível calcular hash do arquivo")
                    return False
                
                stored_hash = self.get_stored_hash()
                
                # Verifica se houve mudança ou se é forçado
                if not force and current_hash == stored_hash:
                    return True  # Sem mudanças
                
                # Carrega dados
                data = self.load_acessos_data()
                if not data:
                    logging.error("[RAMON] Não foi possível carregar dados")
                    return False
                
                # Filtra dados sensíveis antes de enviar
                filtered_data = self.filter_sensitive_data(data)
                
                # Prepara payload para envio
                payload = {
                    "api_key": self.api_key,
                    "timestamp": datetime.now().isoformat(),
                    "hash": current_hash,
                    "data": filtered_data,
                    "total_acessos": len(filtered_data.get("acessos", [])),
                    "total_local": len(data.get("acessos", [])),
                    "filtered_count": len(data.get("acessos", [])) - len(filtered_data.get("acessos", [])),
                    "action": "update",
                    "client_id": "ramon_bot"
                }
                
                # Envia para o servidor com timeout aumentado
                response = self.session.post(
                    f"{self.server_url}/api/sync/acessos",
                    json=payload,
                    timeout=(10, 60),  # (connect_timeout, read_timeout)
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "RamonBotSync/1.0",
                        "Connection": "close"  # Força fechamento da conexão
                    }
                )
                
                if response.status_code == 200:
                    # Armazena novo hash
                    self.store_hash(current_hash)
                    total_local = len(data.get('acessos', []))
                    total_sent = len(filtered_data.get('acessos', []))
                    filtered_count = total_local - total_sent
                    
                    # Log apenas no arquivo
                    if filtered_count > 0:
                        logging.info(f"[RAMON] Sincronização bem-sucedida. Enviados: {total_sent}/{total_local} acessos ({filtered_count} filtrados)")
                    else:
                        logging.info(f"[RAMON] Sincronização bem-sucedida. Total: {total_sent} acessos")
                    return True
                else:
                    logging.warning(f"[RAMON] Tentativa {attempt + 1}: Status {response.status_code}")
                    if attempt == self.max_retries - 1:
                        logging.error(f"[RAMON] Falha após {self.max_retries} tentativas: {response.status_code}")
                        return False
                    
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    ConnectionResetError) as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Backoff exponencial
                    logging.warning(f"[RAMON] Tentativa {attempt + 1} falhou: {type(e).__name__}. Tentando novamente em {delay}s...")
                    time.sleep(delay)
                else:
                    logging.error(f"[RAMON] Falha definitiva após {self.max_retries} tentativas: {e}")
                    return False
                    
            except requests.exceptions.RequestException as e:
                logging.error(f"[RAMON] Erro de requisição: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    return False
                    
            except Exception as e:
                logging.error(f"[RAMON] Erro inesperado na sincronização: {e}")
                return False
        
        return False
    
    def periodic_sync(self):
        """Thread para sincronização periódica com recuperação automática"""
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while self.is_running:
            try:
                success = self.sync_to_server()
                if success:
                    consecutive_failures = 0
                    time.sleep(self.sync_interval)
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        # Aumenta o intervalo após muitas falhas consecutivas
                        extended_interval = self.sync_interval * 3
                        logging.warning(f"[RAMON] {consecutive_failures} falhas consecutivas. Aumentando intervalo para {extended_interval}s")
                        time.sleep(extended_interval)
                        consecutive_failures = 0  # Reset após pausa estendida
                    else:
                        time.sleep(self.sync_interval)
                        
            except Exception as e:
                consecutive_failures += 1
                logging.error(f"[RAMON] Erro crítico na sincronização periódica: {e}")
                # Pausa mais longa em caso de erro crítico
                time.sleep(min(self.sync_interval * 2, 120))
    
    def start_monitoring(self):
        """Inicia o monitoramento do arquivo"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Thread para sincronização periódica (sem sincronização inicial bloqueante)
        self.sync_thread = threading.Thread(target=self.periodic_sync, daemon=True)
        self.sync_thread.start()
        
        logging.info("[RAMON] Sistema de sincronização iniciado")
    
    def stop_monitoring(self):
        """Para o monitoramento"""
        self.is_running = False
        logging.info("[RAMON] Sistema de sincronização parado")
    
    def get_sync_status(self):
        """Retorna status da sincronização"""
        current_hash = self.calculate_file_hash()
        stored_hash = self.get_stored_hash()
        
        return {
            "is_running": self.is_running,
            "current_hash": current_hash,
            "stored_hash": stored_hash,
            "needs_sync": current_hash != stored_hash,
            "server_url": self.server_url,
            "client_id": "ramon_bot"
        }

# Instância global do gerenciador
ramon_sync_manager = RamonSyncManager()

def start_ramon_sync():
    """Função para iniciar o sistema de sincronização do Ramon"""
    ramon_sync_manager.start_monitoring()

def stop_ramon_sync():
    """Função para parar o sistema de sincronização do Ramon"""
    ramon_sync_manager.stop_monitoring()

def force_ramon_sync():
    """Força uma sincronização imediata do Ramon"""
    return ramon_sync_manager.sync_to_server(force=True)

def get_ramon_sync_status():
    """Retorna status da sincronização do Ramon"""
    return ramon_sync_manager.get_sync_status()
