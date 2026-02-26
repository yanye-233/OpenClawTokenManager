#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw Token CLI 工具 v3.1
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import deque

OPENCLAW_DIR = Path.home() / ".openclaw"
SESSIONS_DIR = OPENCLAW_DIR / "agents" / "main" / "sessions"
SESSIONS_JSON = SESSIONS_DIR / "sessions.json"
BACKUP_DIR = SESSIONS_DIR / "backups"

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class TokenCLI:
    def __init__(self):
        self.current_session_id = None
        self.current_jsonl_path = None
        self.initial_line_count = 0
        BACKUP_DIR.mkdir(exist_ok=True)
        
    def list_sessions(self):
        """列出所有会话"""
        print(f"{Colors.BOLD}可用会话列表:{Colors.ENDC}")
        print("-" * 60)
        
        try:
            if SESSIONS_JSON.exists():
                with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for key, value in data.items():
                    if key.startswith("agent:"):
                        session_id = value.get('sessionId', 'unknown')[:20]
                        model = value.get('model', 'unknown')
                        total = value.get('totalTokens', 0)
                        print(f"{Colors.CYAN}{session_id}...{Colors.ENDC} | {model} | {total} tokens")
        except Exception as e:
            print(f"{Colors.RED}错误: {e}{Colors.ENDC}")
            
    def show_session(self, session_id=None):
        """显示会话详情"""
        try:
            if SESSIONS_JSON.exists():
                with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for key, value in data.items():
                    sid = value.get('sessionId', '')
                    if not session_id or sid.startswith(session_id) or session_id in sid:
                        print(f"{Colors.BOLD}会话:{Colors.ENDC} {value.get('sessionId')}")
                        print(f"模型: {value.get('modelProvider')}/{value.get('model')}")
                        
                        total = value.get('totalTokens', 0)
                        context = value.get('contextTokens', 262144)
                        color = Colors.GREEN if total < 30000 else (Colors.YELLOW if total < 60000 else Colors.RED)
                        print(f"Token: {color}{total:,}{Colors.ENDC} / {context:,} ({(total/context)*100:.1f}%)")
                        
                        jsonl_path = SESSIONS_DIR / f"{sid}.jsonl"
                        if jsonl_path.exists():
                            lines = sum(1 for _ in open(jsonl_path, 'r', encoding='utf-8', errors='ignore'))
                            print(f"行数: {lines}")
                        print()
                        
                        if session_id:
                            self.current_session_id = sid
                            self.current_jsonl_path = jsonl_path
                            break
        except Exception as e:
            print(f"{Colors.RED}错误: {e}{Colors.ENDC}")
            
    def show_history(self, session_id=None, count=10, filter_role=None):
        """显示历史记录"""
        sid = session_id or self.current_session_id
        if not sid:
            print(f"{Colors.RED}错误: 请指定会话ID{Colors.ENDC}")
            return
            
        # 查找完整ID
        jsonl_path = SESSIONS_DIR / f"{sid}.jsonl"
        if not jsonl_path.exists():
            try:
                with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        full_sid = value.get('sessionId', '')
                        if full_sid.startswith(sid) or sid in full_sid:
                            sid = full_sid
                            jsonl_path = SESSIONS_DIR / f"{sid}.jsonl"
                            break
            except:
                pass
                
        if not jsonl_path.exists():
            print(f"{Colors.RED}错误: 文件不存在{Colors.ENDC}")
            return
            
        print(f"{Colors.BOLD}最近 {count} 条消息:{Colors.ENDC}")
        print("-" * 60)
        
        try:
            with open(jsonl_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            messages = []
            for line in reversed(lines):
                try:
                    data = json.loads(line.strip())
                    if data.get('type') == 'message':
                        msg = data.get('message', {})
                        role = msg.get('role', 'unknown')
                        if filter_role and role != filter_role:
                            continue
                            
                        content = msg.get('content', [])
                        text = ""
                        if content and isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get('type') == 'text':
                                    text = item.get('text', '')
                                    break
                        
                        messages.append({'role': role, 'text': text[:100]})
                        if len(messages) >= count:
                            break
                except:
                    pass
                    
            for i, msg in enumerate(reversed(messages), 1):
                color = Colors.GREEN if msg['role'] == 'user' else (Colors.BLUE if msg['role'] == 'assistant' else Colors.YELLOW)
                print(f"{i}. {color}[{msg['role']}]{Colors.ENDC} {msg['text']}...")
                
        except Exception as e:
            print(f"{Colors.RED}错误: {e}{Colors.ENDC}")
            
    def backup_file(self, session_id=None):
        """备份文件"""
        sid = session_id or self.current_session_id
        if not sid:
            print(f"{Colors.RED}错误: 请指定会话ID{Colors.ENDC}")
            return
            
        jsonl_path = SESSIONS_DIR / f"{sid}.jsonl"
        if not jsonl_path.exists():
            print(f"{Colors.RED}错误: 文件不存在{Colors.ENDC}")
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{sid}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(jsonl_path, backup_path)
            print(f"{Colors.GREEN}已备份到: {backup_path}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}错误: {e}{Colors.ENDC}")

def main():
    parser = argparse.ArgumentParser(description='OpenClaw Token CLI v3.1')
    parser.add_argument('command', choices=['list', 'show', 'history', 'backup'])
    parser.add_argument('-s', '--session', help='会话ID')
    parser.add_argument('-n', '--count', type=int, default=10)
    parser.add_argument('--filter', choices=['user', 'assistant', 'toolResult'])
    
    args = parser.parse_args()
    cli = TokenCLI()
    
    if args.command == 'list':
        cli.list_sessions()
    elif args.command == 'show':
        cli.show_session(args.session)
    elif args.command == 'history':
        cli.show_history(args.session, args.count, args.filter)
    elif args.command == 'backup':
        cli.backup_file(args.session)

if __name__ == "__main__":
    main()
