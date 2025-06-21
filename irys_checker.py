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
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from web3 import Web3
from web3.middleware import geth_poa_middleware
import requests
from colorama import init, Fore, Style
from tabulate import tabulate
import keyboard

# 初始化colorama
init()

class IrysChecker:
    def __init__(self):
        # Irys Testnet 配置
        self.rpc_url = "https://testnet-rpc.irys.xyz/v1/execution-rpc"
        self.chain_id = 1270
        self.symbol = "IRYS"
        self.explorer = "https://testnet-explorer.irys.xyz"
        
        # 备用RPC URL列表
        self.backup_rpc_urls = [
            "https://testnet-rpc.irys.xyz/v1/execution-rpc",
            "https://testnet-rpc.irys.xyz/execution-rpc",
            "https://rpc.testnet.irys.xyz/v1/execution-rpc"
        ]
        
        # 初始化Web3连接
        self.w3 = None
        self._init_web3_connection()
        
        # 钱包数据
        self.wallets = []
        self.csv_file_path = ""
        
    def _init_web3_connection(self):
        """初始化Web3连接，支持多个RPC端点重试"""
        print(f"{Fore.CYAN}正在连接到Irys Network Testnet...{Style.RESET_ALL}")
        
        for i, rpc_url in enumerate(self.backup_rpc_urls):
            try:
                print(f"尝试连接到: {rpc_url}")
                
                # 创建Web3连接，增加超时设置
                request_kwargs = {
                    'timeout': 30,
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
                if w3_test.is_connected():
                    # 尝试获取chain ID验证
                    try:
                        actual_chain_id = w3_test.eth.chain_id
                        if actual_chain_id == self.chain_id:
                            self.w3 = w3_test
                            self.rpc_url = rpc_url
                            print(f"{Fore.GREEN}✅ 成功连接到Irys Testnet{Style.RESET_ALL}")
                            print(f"{Fore.GREEN}📡 RPC: {rpc_url}{Style.RESET_ALL}")
                            print(f"{Fore.GREEN}🔗 Chain ID: {actual_chain_id}{Style.RESET_ALL}")
                            return
                        else:
                            print(f"{Fore.YELLOW}⚠️  Chain ID不匹配: 期望 {self.chain_id}, 实际 {actual_chain_id}{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠️  无法获取Chain ID: {str(e)}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}⚠️  连接测试失败{Style.RESET_ALL}")
                    
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  连接失败: {str(e)}{Style.RESET_ALL}")
                
            if i < len(self.backup_rpc_urls) - 1:
                print(f"{Fore.CYAN}尝试下一个RPC端点...{Style.RESET_ALL}")
                time.sleep(2)
        
        # 如果所有RPC都失败了
        print(f"\n{Fore.RED}❌ 无法连接到任何Irys网络RPC端点{Style.RESET_ALL}")
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
                
            df = pd.read_csv(file_path)
            
            # 检查必要的列
            required_columns = ['index', 'address', 'privateKey']
            for col in required_columns:
                if col not in df.columns:
                    print(f"{Fore.RED}❌ CSV文件缺少必要的列: {col}{Style.RESET_ALL}")
                    return False
            
            self.wallets = []
            for _, row in df.iterrows():
                wallet_info = {
                    'index': int(row['index']),
                    'address': row['address'],
                    'private_key': row['privateKey'],
                    'balance': None
                }
                
                # 验证地址格式
                if not self.w3.is_address(wallet_info['address']):
                    print(f"{Fore.YELLOW}⚠️  地址格式不正确: {wallet_info['address']}{Style.RESET_ALL}")
                    continue
                    
                self.wallets.append(wallet_info)
            
            self.csv_file_path = file_path
            print(f"{Fore.GREEN}✅ 成功加载 {len(self.wallets)} 个钱包{Style.RESET_ALL}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ 加载CSV文件时出错: {str(e)}{Style.RESET_ALL}")
            return False
    
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
        for wallet in self.wallets:
            print(f"查询中: {wallet['address'][:10]}...", end='\r')
            balance = self.get_balance(wallet['address'])
            wallet['balance'] = balance
            if balance is not None:
                total_balance += balance
        
        # 创建表格数据
        table_data = []
        for wallet in self.wallets:
            balance_str = f"{wallet['balance']:.6f} {self.symbol}" if wallet['balance'] is not None else "获取失败"
            table_data.append([
                wallet['index'],
                f"{wallet['address'][:10]}...{wallet['address'][-10:]}",
                balance_str
            ])
        
        # 显示余额表格
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 钱包余额查询结果{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        headers = ['序号', '钱包地址', '余额']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        print(f"\n{Fore.GREEN}💰 总余额: {total_balance:.6f} {self.symbol}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
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
            "📁 加载钱包CSV文件",
            "💰 查看所有钱包余额", 
            "📤 多对一转账（归集）",
            "📤 一对多转账",
            "ℹ️  显示网络信息",
            "❌ 退出程序"
        ]
        
        current_selection = 0
        
        while True:
            # 清屏
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # 显示标题
            print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}🔗 Irys Network Testnet 钱包管理工具{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            
            if self.wallets:
                print(f"{Fore.GREEN}📂 已加载钱包: {len(self.wallets)} 个{Style.RESET_ALL}")
                print(f"{Fore.GREEN}📄 CSV文件: {self.csv_file_path}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}📂 未加载钱包文件{Style.RESET_ALL}")
            
            print(f"\n{Fore.CYAN}网络信息:{Style.RESET_ALL}")
            print(f"  RPC: {self.rpc_url}")
            print(f"  Chain ID: {self.chain_id}")
            print(f"  符号: {self.symbol}")
            
            print(f"\n{Fore.CYAN}请选择操作 (使用 ↑↓ 键选择，回车确认):{Style.RESET_ALL}")
            
            # 显示菜单选项
            for i, option in enumerate(menu_options):
                if i == current_selection:
                    print(f"{Fore.BLACK}{Style.BRIGHT}➤ {option}{Style.RESET_ALL}")
                else:
                    print(f"  {option}")
            
            # 等待用户输入
            try:
                key = keyboard.read_event()
                if key.event_type == keyboard.KEY_DOWN:
                    if key.name == 'up':
                        current_selection = (current_selection - 1) % len(menu_options)
                    elif key.name == 'down':
                        current_selection = (current_selection + 1) % len(menu_options)
                    elif key.name == 'enter':
                        return current_selection
                    elif key.name == 'q' or key.name == 'esc':
                        return len(menu_options) - 1  # 退出
            except:
                # 如果keyboard不可用，降级到输入模式
                print(f"\n{Fore.YELLOW}⚠️  检测到不支持键盘导航，切换到输入模式{Style.RESET_ALL}")
                for i, option in enumerate(menu_options):
                    print(f"{i+1}. {option}")
                try:
                    choice = int(input(f"\n请输入选择 (1-{len(menu_options)}): ")) - 1
                    if 0 <= choice < len(menu_options):
                        return choice
                    else:
                        print(f"{Fore.RED}❌ 选择无效{Style.RESET_ALL}")
                        input("按回车继续...")
                except ValueError:
                    print(f"{Fore.RED}❌ 请输入数字{Style.RESET_ALL}")
                    input("按回车继续...")
    
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
                
                if choice == 0:  # 加载CSV文件
                    print(f"\n{Fore.CYAN}请输入CSV文件路径 (例: wallets_example.csv): {Style.RESET_ALL}", end='')
                    file_path = input().strip()
                    if file_path:
                        self.load_wallets_from_csv(file_path)
                    input("按回车继续...")
                
                elif choice == 1:  # 查看余额
                    self.check_all_balances()
                    input("按回车继续...")
                
                elif choice == 2:  # 多对一转账
                    self.bulk_transfer_many_to_one()
                    input("按回车继续...")
                
                elif choice == 3:  # 一对多转账
                    self.bulk_transfer_one_to_many()
                    input("按回车继续...")
                
                elif choice == 4:  # 显示网络信息
                    self.show_network_info()
                
                elif choice == 5:  # 退出
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