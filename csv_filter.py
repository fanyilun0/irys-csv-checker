#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV文件过滤工具
功能：过滤出余额大于0的钱包地址，生成新的CSV文件
"""

import os
import pandas as pd
from decimal import Decimal
from typing import List, Dict, Optional
from colorama import init, Fore, Style
from datetime import datetime

# 初始化colorama
init()

class CSVFilter:
    def __init__(self):
        self.symbol = "IRYS"
    
    def filter_wallets_with_balance(self, wallets: List[Dict], min_balance: Decimal = Decimal('0')) -> List[Dict]:
        """
        过滤出余额大于指定数值的钱包
        
        Args:
            wallets: 钱包列表，每个钱包包含地址、私钥、余额等信息
            min_balance: 最小余额阈值，默认为0
            
        Returns:
            过滤后的钱包列表
        """
        filtered_wallets = []
        
        for wallet in wallets:
            balance = wallet.get('balance')
            
            # 跳过没有余额信息的钱包
            if balance is None:
                continue
            
            # 检查余额是否大于阈值
            if balance > min_balance:
                filtered_wallets.append(wallet)
        
        return filtered_wallets
    
    def export_filtered_wallets_to_csv(self, filtered_wallets: List[Dict], output_path: str) -> bool:
        """
        将过滤后的钱包数据导出为CSV文件
        
        Args:
            filtered_wallets: 过滤后的钱包列表
            output_path: 输出文件路径
            
        Returns:
            是否成功导出
        """
        try:
            if not filtered_wallets:
                print(f"{Fore.YELLOW}⚠️  没有符合条件的钱包数据{Style.RESET_ALL}")
                return False
            
            # 准备CSV数据
            csv_data = []
            for i, wallet in enumerate(filtered_wallets, 1):
                csv_data.append({
                    'index': i,
                    'address': wallet['address'],
                    'privateKey': wallet['private_key'],
                    'balance': f"{wallet['balance']:.6f}",
                    'source_file': wallet.get('source_file', '未知')
                })
            
            # 创建DataFrame
            df = pd.DataFrame(csv_data)
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 导出为CSV文件
            df.to_csv(output_path, index=False, encoding='utf-8')
            
            print(f"{Fore.GREEN}✅ 成功导出 {len(filtered_wallets)} 个钱包到 {output_path}{Style.RESET_ALL}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ 导出CSV文件时出错: {str(e)}{Style.RESET_ALL}")
            return False
    
    def generate_output_filename(self, base_name: str = "filtered_wallets") -> str:
        """
        生成输出文件名，包含时间戳
        
        Args:
            base_name: 基础文件名
            
        Returns:
            包含时间戳的文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base_name}_{timestamp}.csv"
    
    def show_filter_summary(self, original_count: int, filtered_count: int, zero_balance_count: int, failed_count: int):
        """
        显示过滤结果摘要
        
        Args:
            original_count: 原始钱包数量
            filtered_count: 过滤后钱包数量
            zero_balance_count: 零余额钱包数量
            failed_count: 获取余额失败的钱包数量
        """
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 钱包过滤结果摘要{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        print(f"{Fore.BLUE}📂 原始钱包总数: {Style.RESET_ALL}{original_count}")
        print(f"{Fore.GREEN}✅ 有余额钱包: {Style.RESET_ALL}{filtered_count}")
        print(f"{Fore.YELLOW}⭕ 零余额钱包: {Style.RESET_ALL}{zero_balance_count}")
        
        if failed_count > 0:
            print(f"{Fore.RED}❌ 查询失败钱包: {Style.RESET_ALL}{failed_count}")
        
        if filtered_count > 0:
            retention_rate = (filtered_count / original_count) * 100
            print(f"{Fore.CYAN}📈 保留率: {Style.RESET_ALL}{retention_rate:.1f}%")
        
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    def filter_and_export(self, wallets: List[Dict], output_path: Optional[str] = None, min_balance: Decimal = Decimal('0')) -> bool:
        """
        一键过滤并导出钱包数据
        
        Args:
            wallets: 原始钱包列表
            output_path: 输出文件路径，如果为None则自动生成
            min_balance: 最小余额阈值
            
        Returns:
            是否成功
        """
        if not wallets:
            print(f"{Fore.RED}❌ 没有钱包数据{Style.RESET_ALL}")
            return False
        
        print(f"{Fore.CYAN}🔍 开始过滤钱包数据...{Style.RESET_ALL}")
        
        # 统计数据
        original_count = len(wallets)
        zero_balance_count = 0
        failed_count = 0
        
        # 过滤钱包
        filtered_wallets = []
        for wallet in wallets:
            balance = wallet.get('balance')
            
            if balance is None:
                failed_count += 1
                continue
            
            if balance <= min_balance:
                zero_balance_count += 1
                continue
            
            filtered_wallets.append(wallet)
        
        filtered_count = len(filtered_wallets)
        
        # 显示过滤摘要
        self.show_filter_summary(original_count, filtered_count, zero_balance_count, failed_count)
        
        # 如果没有符合条件的钱包，直接返回
        if filtered_count == 0:
            print(f"{Fore.YELLOW}⚠️  没有找到余额大于 {min_balance} {self.symbol} 的钱包{Style.RESET_ALL}")
            return False
        
        # 生成输出文件路径
        if output_path is None:
            output_path = self.generate_output_filename()
        
        # 导出过滤后的数据
        return self.export_filtered_wallets_to_csv(filtered_wallets, output_path)
    
    def interactive_filter(self, wallets: List[Dict]) -> bool:
        """
        交互式过滤钱包
        
        Args:
            wallets: 钱包列表
            
        Returns:
            是否成功完成操作
        """
        if not wallets:
            print(f"{Fore.RED}❌ 没有钱包数据{Style.RESET_ALL}")
            return False
        
        print(f"\n{Fore.CYAN}🔍 钱包过滤配置{Style.RESET_ALL}")
        
        # 获取最小余额阈值
        print(f"{Fore.CYAN}请输入最小余额阈值 ({self.symbol}) [默认: 0]: {Style.RESET_ALL}", end='')
        min_balance_input = input().strip()
        
        try:
            min_balance = Decimal('0') if not min_balance_input else Decimal(min_balance_input)
        except:
            print(f"{Fore.RED}❌ 余额格式不正确，使用默认值 0{Style.RESET_ALL}")
            min_balance = Decimal('0')
        
        # 获取输出文件路径
        print(f"{Fore.CYAN}请输入输出文件路径 [默认: 自动生成]: {Style.RESET_ALL}", end='')
        output_path = input().strip()
        
        if not output_path:
            output_path = self.generate_output_filename()
        
        # 确保文件扩展名为.csv
        if not output_path.lower().endswith('.csv'):
            output_path += '.csv'
        
        print(f"{Fore.GREEN}📁 输出文件: {output_path}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}💰 最小余额: {min_balance} {self.symbol}{Style.RESET_ALL}")
        
        # 确认操作
        print(f"\n{Fore.CYAN}确认执行过滤操作？(y/n): {Style.RESET_ALL}", end='')
        confirm = input().strip().lower()
        
        if confirm not in ['y', 'yes', '是']:
            print(f"{Fore.YELLOW}⚠️  操作已取消{Style.RESET_ALL}")
            return False
        
        # 执行过滤和导出
        return self.filter_and_export(wallets, output_path, min_balance) 