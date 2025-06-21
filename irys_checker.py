#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Irys Network Testnet 钱包管理工具
功能：批量查看余额、批量转账（归集）
"""

import os
import sys
import json
import time
import pandas as pd
import glob
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from web3 import Web3
from web3.middleware import geth_poa_middleware
import requests
from colorama import init, Fore, Style
from tabulate import tabulate
# 使用标准输入处理用户交互

# 初始化colorama
init()

class IrysChecker:
    def __init__(self):
        # Irys Testnet 配置
        self.rpc_url = "https://testnet-rpc.irys.xyz/v1/execution-rpc"
        self.chain_id = 1270
        self.symbol = "IRYS"
        self.explorer = "https://testnet-explorer.irys.xyz"
        
        # RPC URL（根据测试只保留有效的端点）
        self.rpc_urls = [
            "https://testnet-rpc.irys.xyz/v1/execution-rpc"
        ]
        
        # 初始化Web3连接
        self.w3 = None
        self._init_web3_connection()
        
        # 钱包数据
        self.wallets = []
        self.loaded_files = []  # 记录已加载的文件信息
        
    def _init_web3_connection(self):
        """初始化Web3连接"""
        print(f"{Fore.CYAN}正在连接到Irys Network Testnet...{Style.RESET_ALL}")
        
        rpc_url = self.rpc_urls[0]  # 只使用有效的RPC端点
        try:
            print(f"连接到: {rpc_url}")
            
            # 创建Web3连接，增加超时设置
            request_kwargs = {
                'timeout': 15,
                'headers': {
                    'User-Agent': 'Irys-Checker/1.0',
                    'Content-Type': 'application/json'
                }
            }
            
            provider = Web3.HTTPProvider(rpc_url, request_kwargs=request_kwargs)
            w3_test = Web3(provider)
            
            # 添加PoA中间件（如果需要）
            w3_test.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            # 测试连接
            latest_block = w3_test.eth.block_number
            print(f"{Fore.GREEN}✅ 连接成功! 最新区块: {latest_block}{Style.RESET_ALL}")
            
            # 验证chain ID
            actual_chain_id = w3_test.eth.chain_id
            print(f"{Fore.GREEN}🔗 Chain ID: {actual_chain_id}{Style.RESET_ALL}")
            
            if actual_chain_id == self.chain_id:
                self.w3 = w3_test
                self.rpc_url = rpc_url
                print(f"{Fore.GREEN}✅ 成功连接到Irys Testnet{Style.RESET_ALL}")
                return
            else:
                print(f"{Fore.YELLOW}⚠️  Chain ID不匹配: 期望 {self.chain_id}, 实际 {actual_chain_id}{Style.RESET_ALL}")
                raise Exception(f"Chain ID不匹配")
                
        except Exception as e:
            print(f"{Fore.RED}❌ 连接失败: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}可能的原因：{Style.RESET_ALL}")
            print(f"  1. 网络连接问题")
            print(f"  2. Irys Testnet维护中")
            print(f"  3. 防火墙或代理设置")
            print(f"\n{Fore.CYAN}建议：{Style.RESET_ALL}")
            print(f"  1. 检查网络连接")
            print(f"  2. 稍后重试")
            print(f"  3. 查看Irys官方状态: https://docs.irys.xyz")
            
            # 询问用户是否继续（离线模式）
            print(f"\n{Fore.CYAN}是否以离线模式继续？(y/n): {Style.RESET_ALL}", end='')
            choice = input().strip().lower()
            if choice == 'y' or choice == 'yes':
                print(f"{Fore.YELLOW}⚠️  进入离线模式，某些功能将不可用{Style.RESET_ALL}")
                # 创建一个虚拟的Web3连接用于地址验证
                self.w3 = Web3()
            else:
                sys.exit(1)
        
    def load_wallets_from_csv(self, file_path: str) -> bool:
        """从CSV文件加载钱包信息"""
        try:
            if not os.path.exists(file_path):
                print(f"{Fore.RED}❌ CSV文件不存在: {file_path}{Style.RESET_ALL}")
                return False
                
            # 读取CSV文件，支持不同的编码格式
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(file_path, encoding='gbk')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding='latin-1')
            
            if df.empty:
                print(f"{Fore.RED}❌ CSV文件为空{Style.RESET_ALL}")
                return False
            
            print(f"{Fore.CYAN}📄 CSV文件包含 {len(df)} 行数据{Style.RESET_ALL}")
            print(f"{Fore.CYAN}📋 CSV文件列名: {list(df.columns)}{Style.RESET_ALL}")
            
            # 检查必要的列（支持不同的列名格式）
            possible_columns = {
                'index': ['index', 'id', 'no', 'num', '序号', '编号'],
                'address': ['address', 'addr', 'wallet', 'publickey', 'public_key', '地址', '钱包地址'],
                'privateKey': ['privateKey', 'private_key', 'privkey', 'key', 'secret', '私钥']
            }
            
            column_mapping = {}
            for required, possible in possible_columns.items():
                found = False
                for col in df.columns:
                    if col.lower().strip() in [p.lower() for p in possible]:
                        column_mapping[required] = col
                        found = True
                        break
                if not found:
                    print(f"{Fore.RED}❌ 未找到必要的列: {required}，可能的列名: {possible}{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}📋 当前文件列名: {list(df.columns)}{Style.RESET_ALL}")
                    return False
            
            print(f"{Fore.GREEN}✅ 列映射: {column_mapping}{Style.RESET_ALL}")
            
            self.wallets = []
            valid_count = 0
            invalid_count = 0
            
            for idx, row in df.iterrows():
                try:
                    # 提取数据，处理可能的空值
                    index_val = row[column_mapping['index']]
                    address_val = str(row[column_mapping['address']]).strip()
                    private_key_val = str(row[column_mapping['privateKey']]).strip()
                    
                    # 跳过空行
                    if pd.isna(index_val) or not address_val or not private_key_val or address_val == 'nan' or private_key_val == 'nan':
                        print(f"{Fore.YELLOW}⚠️  跳过空行 {idx+1}{Style.RESET_ALL}")
                        invalid_count += 1
                        continue
                    
                    wallet_info = {
                        'index': int(float(index_val)) if not pd.isna(index_val) else idx + 1,
                        'address': address_val,
                        'private_key': private_key_val,
                        'balance': None
                    }
                    
                    # 验证地址格式（如果连接到网络）
                    if self.w3 and hasattr(self.w3, 'is_address'):
                        if not self.w3.is_address(wallet_info['address']):
                            print(f"{Fore.YELLOW}⚠️  地址格式不正确 (行{idx+1}): {wallet_info['address']}{Style.RESET_ALL}")
                            invalid_count += 1
                            continue
                    else:
                        # 简单的以太坊地址格式检查
                        if not (wallet_info['address'].startswith('0x') and len(wallet_info['address']) == 42):
                            print(f"{Fore.YELLOW}⚠️  地址格式可能不正确 (行{idx+1}): {wallet_info['address']}{Style.RESET_ALL}")
                            invalid_count += 1
                            continue
                    
                    # 验证私钥格式
                    if not (wallet_info['private_key'].startswith('0x') and len(wallet_info['private_key']) == 66):
                        print(f"{Fore.YELLOW}⚠️  私钥格式可能不正确 (行{idx+1}): {wallet_info['private_key'][:10]}...{Style.RESET_ALL}")
                        invalid_count += 1
                        continue
                    
                    self.wallets.append(wallet_info)
                    valid_count += 1
                    
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️  处理行{idx+1}时出错: {str(e)}{Style.RESET_ALL}")
                    invalid_count += 1
                    continue
            
            self.csv_file_path = file_path
            print(f"\n{Fore.GREEN}✅ 成功加载 {valid_count} 个有效钱包{Style.RESET_ALL}")
            if invalid_count > 0:
                print(f"{Fore.YELLOW}⚠️  跳过 {invalid_count} 个无效行{Style.RESET_ALL}")
            
            return valid_count > 0
            
        except Exception as e:
            print(f"{Fore.RED}❌ 加载CSV文件时出错: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}请检查文件格式和内容{Style.RESET_ALL}")
            return False
    
    def scan_directory_for_csv(self, directory_path: str) -> List[str]:
        """扫描目录下的所有CSV文件"""
        try:
            if not os.path.exists(directory_path):
                print(f"{Fore.RED}❌ 目录不存在: {directory_path}{Style.RESET_ALL}")
                return []
            
            if not os.path.isdir(directory_path):
                print(f"{Fore.RED}❌ 不是有效目录: {directory_path}{Style.RESET_ALL}")
                return []
            
            # 搜索CSV文件
            csv_patterns = [
                os.path.join(directory_path, "*.csv"),
                os.path.join(directory_path, "*.CSV"),
                os.path.join(directory_path, "**", "*.csv"),
                os.path.join(directory_path, "**", "*.CSV")
            ]
            
            csv_files = []
            for pattern in csv_patterns:
                csv_files.extend(glob.glob(pattern, recursive=True))
            
            # 去重并排序
            csv_files = sorted(list(set(csv_files)))
            
            if not csv_files:
                print(f"{Fore.YELLOW}⚠️  在目录 {directory_path} 中未找到CSV文件{Style.RESET_ALL}")
                return []
            
            print(f"{Fore.GREEN}📂 在目录中找到 {len(csv_files)} 个CSV文件{Style.RESET_ALL}")
            return csv_files
            
        except Exception as e:
            print(f"{Fore.RED}❌ 扫描目录时出错: {str(e)}{Style.RESET_ALL}")
            return []
    
    def select_csv_files(self, csv_files: List[str]) -> List[str]:
        """让用户选择要加载的CSV文件"""
        if not csv_files:
            return []
        
        print(f"\n{Fore.CYAN}📋 找到的CSV文件列表:{Style.RESET_ALL}")
        for i, file_path in enumerate(csv_files, 1):
            file_size = os.path.getsize(file_path) / 1024  # KB
            file_name = os.path.basename(file_path)
            print(f"{i:2d}. {file_name} ({file_size:.1f} KB)")
        
        print(f"\n{Fore.CYAN}选择操作:{Style.RESET_ALL}")
        print("A. 加载所有文件")
        print("S. 选择特定文件 (例: 1,3,5 或 1-5)")
        print("Q. 返回主菜单")
        
        while True:
            choice = input(f"\n请输入选择: ").strip().upper()
            
            if choice == 'Q':
                return []
            elif choice == 'A':
                return csv_files
            elif choice == 'S':
                return self._select_specific_files(csv_files)
            else:
                print(f"{Fore.RED}❌ 无效选择，请输入 A、S 或 Q{Style.RESET_ALL}")
    
    def _select_specific_files(self, csv_files: List[str]) -> List[str]:
        """处理特定文件选择"""
        while True:
            selection = input(f"{Fore.CYAN}请输入文件编号 (例: 1,3,5 或 1-5): {Style.RESET_ALL}").strip()
            
            if not selection:
                return []
            
            try:
                selected_files = []
                parts = selection.split(',')
                
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        # 处理范围选择 (例: 1-5)
                        start, end = map(int, part.split('-'))
                        for i in range(start, end + 1):
                            if 1 <= i <= len(csv_files):
                                selected_files.append(csv_files[i-1])
                    else:
                        # 处理单个选择
                        i = int(part)
                        if 1 <= i <= len(csv_files):
                            selected_files.append(csv_files[i-1])
                        else:
                            print(f"{Fore.YELLOW}⚠️  编号 {i} 超出范围{Style.RESET_ALL}")
                
                # 去重
                selected_files = list(dict.fromkeys(selected_files))  # 保持顺序的去重
                
                if selected_files:
                    print(f"{Fore.GREEN}✅ 已选择 {len(selected_files)} 个文件{Style.RESET_ALL}")
                    for file_path in selected_files:
                        print(f"   - {os.path.basename(file_path)}")
                    return selected_files
                else:
                    print(f"{Fore.YELLOW}⚠️  没有选择有效文件{Style.RESET_ALL}")
                    
            except ValueError:
                print(f"{Fore.RED}❌ 输入格式错误，请使用类似 1,3,5 或 1-5 的格式{Style.RESET_ALL}")
    
    def load_multiple_csv_files(self, file_paths: List[str]) -> bool:
        """批量加载多个CSV文件"""
        if not file_paths:
            return False
        
        print(f"\n{Fore.CYAN}📂 开始批量加载 {len(file_paths)} 个CSV文件...{Style.RESET_ALL}")
        
        all_wallets = []
        successful_files = []
        failed_files = []
        
        for i, file_path in enumerate(file_paths, 1):
            print(f"\n{Fore.CYAN}正在处理文件 {i}/{len(file_paths)}: {os.path.basename(file_path)}{Style.RESET_ALL}")
            
            # 临时保存当前钱包数据
            temp_wallets = self.wallets.copy()
            temp_files = self.loaded_files.copy()
            
            # 清空当前数据来加载单个文件
            self.wallets = []
            
            if self._load_single_csv_file(file_path):
                # 为每个钱包添加来源文件信息
                for wallet in self.wallets:
                    wallet['source_file'] = os.path.basename(file_path)
                
                all_wallets.extend(self.wallets)
                successful_files.append({
                    'path': file_path,
                    'name': os.path.basename(file_path),
                    'count': len(self.wallets)
                })
                print(f"{Fore.GREEN}✅ 成功加载 {len(self.wallets)} 个钱包{Style.RESET_ALL}")
            else:
                failed_files.append(file_path)
                print(f"{Fore.RED}❌ 加载失败{Style.RESET_ALL}")
        
        # 恢复所有成功加载的钱包数据
        self.wallets = all_wallets
        self.loaded_files = successful_files
        
        # 显示汇总信息
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 批量加载完成汇总{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        if successful_files:
            print(f"{Fore.GREEN}✅ 成功加载 {len(successful_files)} 个文件，共 {len(self.wallets)} 个钱包:{Style.RESET_ALL}")
            for file_info in successful_files:
                print(f"   📄 {file_info['name']}: {file_info['count']} 个钱包")
        
        if failed_files:
            print(f"{Fore.RED}❌ 加载失败 {len(failed_files)} 个文件:{Style.RESET_ALL}")
            for file_path in failed_files:
                print(f"   📄 {os.path.basename(file_path)}")
        
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        return len(successful_files) > 0
    
    def _load_single_csv_file(self, file_path: str) -> bool:
        """加载单个CSV文件（内部使用）"""
        return self.load_wallets_from_csv(file_path)
    
    def get_balance(self, address: str) -> Optional[Decimal]:
        """获取指定地址的余额"""
        if not self.w3 or not hasattr(self.w3.eth, 'get_balance'):
            print(f"{Fore.YELLOW}⚠️  离线模式，无法获取余额: {address}{Style.RESET_ALL}")
            return None
            
        try:
            # 转换为checksum地址
            checksum_address = self.w3.to_checksum_address(address)
            balance_wei = self.w3.eth.get_balance(checksum_address)
            balance_ether = self.w3.from_wei(balance_wei, 'ether')
            return Decimal(str(balance_ether))
        except Exception as e:
            print(f"{Fore.RED}❌ 获取余额失败 {address}: {str(e)}{Style.RESET_ALL}")
            return None
    
    def check_all_balances(self):
        """批量查看所有钱包余额"""
        if not self.wallets:
            print(f"{Fore.YELLOW}⚠️  请先加载钱包CSV文件{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}📊 正在查询钱包余额...{Style.RESET_ALL}")
        
        # 更新余额信息
        total_balance = Decimal('0')
        for i, wallet in enumerate(self.wallets, 1):
            print(f"查询进度: {i}/{len(self.wallets)} - {wallet['address'][:10]}...", end='\r')
            balance = self.get_balance(wallet['address'])
            wallet['balance'] = balance
            if balance is not None:
                total_balance += balance
        
        # 创建表格数据
        table_data = []
        for wallet in self.wallets:
            balance_str = f"{wallet['balance']:.6f} {self.symbol}" if wallet['balance'] is not None else "获取失败"
            source_file = wallet.get('source_file', '未知文件')
            table_data.append([
                wallet['index'],
                f"{wallet['address'][:10]}...{wallet['address'][-10:]}",
                balance_str,
                source_file
            ])
        
        # 显示余额表格
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 钱包余额查询结果{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        
        headers = ['序号', '钱包地址', '余额', '来源文件']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        print(f"\n{Fore.GREEN}💰 总余额: {total_balance:.6f} {self.symbol}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    
    def estimate_gas_price(self) -> int:
        """估算当前gas价格"""
        if not self.w3 or not hasattr(self.w3.eth, 'gas_price'):
            # 离线模式，返回默认值
            return Web3.to_wei(20, 'gwei')
            
        try:
            gas_price = self.w3.eth.gas_price
            return gas_price
        except:
            # 如果获取失败，返回一个默认值
            return Web3.to_wei(20, 'gwei')
    
    def send_transaction(self, from_address: str, private_key: str, to_address: str, amount: Decimal) -> Optional[str]:
        """发送交易"""
        if not self.w3 or not hasattr(self.w3.eth, 'send_raw_transaction'):
            print(f"{Fore.RED}❌ 离线模式，无法发送交易{Style.RESET_ALL}")
            return None
            
        try:
            # 转换地址格式
            from_checksum = self.w3.to_checksum_address(from_address)
            to_checksum = self.w3.to_checksum_address(to_address)
            
            # 获取nonce
            nonce = self.w3.eth.get_transaction_count(from_checksum)
            
            # 获取gas价格
            gas_price = self.estimate_gas_price()
            
            # 构建交易
            transaction = {
                'to': to_checksum,
                'value': self.w3.to_wei(amount, 'ether'),
                'gas': 21000,  # 标准转账gas限制
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            }
            
            # 签名交易
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            
            # 发送交易
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return tx_hash.hex()
            
        except Exception as e:
            print(f"{Fore.RED}❌ 发送交易失败: {str(e)}{Style.RESET_ALL}")
            return None
    
    def bulk_transfer_many_to_one(self):
        """多对一转账（归集）"""
        if not self.wallets:
            print(f"{Fore.YELLOW}⚠️  请先加载钱包CSV文件{Style.RESET_ALL}")
            return
        
        # 获取目标地址
        print(f"{Fore.CYAN}请输入归集目标地址: {Style.RESET_ALL}", end='')
        target_address = input().strip()
        
        if not self.w3.is_address(target_address):
            print(f"{Fore.RED}❌ 目标地址格式不正确{Style.RESET_ALL}")
            return
        
        # 获取保留余额
        print(f"{Fore.CYAN}请输入每个钱包保留的余额 ({self.symbol}) [默认: 0.01]: {Style.RESET_ALL}", end='')
        reserve_balance_input = input().strip()
        reserve_balance = Decimal('0.01') if not reserve_balance_input else Decimal(reserve_balance_input)
        
        print(f"\n{Fore.CYAN}📤 开始归集转账...{Style.RESET_ALL}")
        
        success_count = 0
        failed_count = 0
        
        for wallet in self.wallets:
            # 获取当前余额
            current_balance = self.get_balance(wallet['address'])
            if current_balance is None:
                print(f"{Fore.RED}❌ 无法获取余额: {wallet['address']}{Style.RESET_ALL}")
                failed_count += 1
                continue
            
            # 计算可转账金额
            gas_price = self.estimate_gas_price()
            gas_cost = Decimal(str(self.w3.from_wei(gas_price * 21000, 'ether')))
            transfer_amount = current_balance - reserve_balance - gas_cost
            
            if transfer_amount <= 0:
                print(f"{Fore.YELLOW}⚠️  余额不足，跳过: {wallet['address']} (余额: {current_balance:.6f}){Style.RESET_ALL}")
                continue
            
            print(f"正在转账: {wallet['address'][:10]}... -> {target_address[:10]}... 金额: {transfer_amount:.6f} {self.symbol}")
            
            # 发送交易
            tx_hash = self.send_transaction(
                wallet['address'], 
                wallet['private_key'], 
                target_address, 
                transfer_amount
            )
            
            if tx_hash:
                print(f"{Fore.GREEN}✅ 交易成功: {tx_hash}{Style.RESET_ALL}")
                print(f"   浏览器查看: {self.explorer}/tx/{tx_hash}")
                success_count += 1
            else:
                failed_count += 1
            
            # 添加延迟避免过快发送
            time.sleep(1)
        
        print(f"\n{Fore.CYAN}📊 归集完成统计:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ 成功: {success_count} 笔{Style.RESET_ALL}")
        print(f"{Fore.RED}❌ 失败: {failed_count} 笔{Style.RESET_ALL}")
    
    def bulk_transfer_one_to_many(self):
        """一对多转账"""
        if not self.wallets:
            print(f"{Fore.YELLOW}⚠️  请先加载钱包CSV文件{Style.RESET_ALL}")
            return
        
        # 显示可选的发送方钱包
        print(f"\n{Fore.CYAN}请选择发送方钱包:{Style.RESET_ALL}")
        for i, wallet in enumerate(self.wallets):
            balance = self.get_balance(wallet['address'])
            balance_str = f"{balance:.6f} {self.symbol}" if balance else "获取失败"
            print(f"{i+1}. {wallet['address']} (余额: {balance_str})")
        
        try:
            choice = int(input(f"{Fore.CYAN}请输入选择 (1-{len(self.wallets)}): {Style.RESET_ALL}")) - 1
            if choice < 0 or choice >= len(self.wallets):
                print(f"{Fore.RED}❌ 选择无效{Style.RESET_ALL}")
                return
        except ValueError:
            print(f"{Fore.RED}❌ 请输入数字{Style.RESET_ALL}")
            return
        
        sender_wallet = self.wallets[choice]
        
        # 获取转账金额
        print(f"{Fore.CYAN}请输入每个地址的转账金额 ({self.symbol}): {Style.RESET_ALL}", end='')
        try:
            amount = Decimal(input().strip())
        except:
            print(f"{Fore.RED}❌ 金额格式不正确{Style.RESET_ALL}")
            return
        
        # 排除发送方地址
        receiver_wallets = [w for w in self.wallets if w['address'] != sender_wallet['address']]
        
        print(f"\n{Fore.CYAN}📤 开始一对多转账...{Style.RESET_ALL}")
        print(f"发送方: {sender_wallet['address']}")
        print(f"接收方数量: {len(receiver_wallets)}")
        print(f"单笔金额: {amount} {self.symbol}")
        
        success_count = 0
        failed_count = 0
        
        for receiver in receiver_wallets:
            print(f"正在转账: {sender_wallet['address'][:10]}... -> {receiver['address'][:10]}... 金额: {amount} {self.symbol}")
            
            tx_hash = self.send_transaction(
                sender_wallet['address'], 
                sender_wallet['private_key'], 
                receiver['address'], 
                amount
            )
            
            if tx_hash:
                print(f"{Fore.GREEN}✅ 交易成功: {tx_hash}{Style.RESET_ALL}")
                print(f"   浏览器查看: {self.explorer}/tx/{tx_hash}")
                success_count += 1
            else:
                failed_count += 1
            
            # 添加延迟
            time.sleep(1)
        
        print(f"\n{Fore.CYAN}📊 一对多转账完成统计:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ 成功: {success_count} 笔{Style.RESET_ALL}")
        print(f"{Fore.RED}❌ 失败: {failed_count} 笔{Style.RESET_ALL}")
    
    def show_menu(self):
        """显示主菜单"""
        menu_options = [
            "📁 加载单个CSV文件",
            "📂 批量加载目录中的CSV文件",
            "💰 查看所有钱包余额", 
            "📤 多对一转账（归集）",
            "📤 一对多转账",
            "ℹ️  显示网络信息",
            "❌ 退出程序"
        ]
        
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 显示标题
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}🔗 Irys Network Testnet 钱包管理工具{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        if self.wallets:
            print(f"{Fore.GREEN}📂 已加载钱包: {len(self.wallets)} 个{Style.RESET_ALL}")
            if self.loaded_files:
                print(f"{Fore.GREEN}📄 已加载 {len(self.loaded_files)} 个CSV文件:{Style.RESET_ALL}")
                for file_info in self.loaded_files:
                    print(f"   🗂️  {file_info['name']}: {file_info['count']} 个钱包")
            else:
                # 兼容旧版本数据
                print(f"{Fore.GREEN}📄 已加载文件{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}📂 未加载钱包文件{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}网络信息:{Style.RESET_ALL}")
        print(f"  RPC: {self.rpc_url}")
        print(f"  Chain ID: {self.chain_id}")
        print(f"  符号: {self.symbol}")
        
        print(f"\n{Fore.CYAN}请选择操作:{Style.RESET_ALL}")
        
        # 显示菜单选项
        for i, option in enumerate(menu_options):
            print(f"{i+1}. {option}")
        
        # 等待用户输入
        while True:
            try:
                choice = int(input(f"\n请输入选择 (1-{len(menu_options)}): ")) - 1
                if 0 <= choice < len(menu_options):
                    return choice
                else:
                    print(f"{Fore.RED}❌ 请输入1-{len(menu_options)}之间的数字{Style.RESET_ALL}")
            except (ValueError, KeyboardInterrupt):
                print(f"{Fore.RED}❌ 请输入有效数字{Style.RESET_ALL}")
            except EOFError:
                return len(menu_options) - 1  # 退出
    
    def show_network_info(self):
        """显示网络信息"""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}🔗 Irys Network Testnet 网络信息{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}RPC URL: {Style.RESET_ALL}{self.rpc_url}")
        print(f"{Fore.GREEN}Chain ID: {Style.RESET_ALL}{self.chain_id}")
        print(f"{Fore.GREEN}符号: {Style.RESET_ALL}{self.symbol}")
        print(f"{Fore.GREEN}浏览器: {Style.RESET_ALL}{self.explorer}")
        
        # 获取网络状态
        if not self.w3 or not hasattr(self.w3.eth, 'block_number'):
            print(f"{Fore.YELLOW}连接状态: {Style.RESET_ALL}⚠️  离线模式")
        else:
            try:
                latest_block = self.w3.eth.block_number
                gas_price = self.w3.eth.gas_price
                print(f"{Fore.GREEN}最新区块: {Style.RESET_ALL}{latest_block}")
                print(f"{Fore.GREEN}当前Gas价格: {Style.RESET_ALL}{self.w3.from_wei(gas_price, 'gwei'):.2f} Gwei")
                print(f"{Fore.GREEN}连接状态: {Style.RESET_ALL}✅ 已连接")
            except Exception as e:
                print(f"{Fore.RED}网络状态: {Style.RESET_ALL}❌ 连接异常 ({str(e)})")
        
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        input("\n按回车返回主菜单...")
    
    def run(self):
        """运行主程序"""
        try:
            while True:
                choice = self.show_menu()
                
                if choice == 0:  # 加载单个CSV文件
                    print(f"\n{Fore.CYAN}请输入CSV文件路径 (例: wallets_example.csv): {Style.RESET_ALL}", end='')
                    file_path = input().strip()
                    if file_path:
                        if self.load_wallets_from_csv(file_path):
                            # 更新加载文件信息
                            self.loaded_files = [{
                                'path': file_path,
                                'name': os.path.basename(file_path),
                                'count': len(self.wallets)
                            }]
                    input("按回车继续...")
                
                elif choice == 1:  # 批量加载目录中的CSV文件
                    print(f"\n{Fore.CYAN}请输入目录路径: {Style.RESET_ALL}", end='')
                    dir_path = input().strip()
                    if dir_path:
                        csv_files = self.scan_directory_for_csv(dir_path)
                        if csv_files:
                            selected_files = self.select_csv_files(csv_files)
                            if selected_files:
                                self.load_multiple_csv_files(selected_files)
                    input("按回车继续...")
                
                elif choice == 2:  # 查看余额
                    self.check_all_balances()
                    input("按回车继续...")
                
                elif choice == 3:  # 多对一转账
                    self.bulk_transfer_many_to_one()
                    input("按回车继续...")
                
                elif choice == 4:  # 一对多转账
                    self.bulk_transfer_one_to_many()
                    input("按回车继续...")
                
                elif choice == 5:  # 显示网络信息
                    self.show_network_info()
                
                elif choice == 6:  # 退出
                    print(f"\n{Fore.GREEN}👋 感谢使用！{Style.RESET_ALL}")
                    break
                
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}程序被用户中断{Style.RESET_ALL}")
        except Exception as e:
            print(f"\n{Fore.RED}❌ 程序运行出错: {str(e)}{Style.RESET_ALL}")

def main():
    """主函数"""
    print(f"{Fore.CYAN}正在初始化 Irys Network Testnet 钱包管理工具...{Style.RESET_ALL}")
    
    checker = IrysChecker()
    checker.run()

if __name__ == "__main__":
    main() 