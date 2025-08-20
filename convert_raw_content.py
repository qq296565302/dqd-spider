#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将team_detail_.json中的raw_content字符串转换为JSON格式
处理Unicode转义字符并格式化输出
"""

import json
import re
from datetime import datetime

def convert_unicode_escapes(text):
    """
    转换Unicode转义字符
    """
    # 处理\u002F这样的Unicode转义
    def replace_unicode(match):
        unicode_str = match.group(0)
        try:
            return unicode_str.encode().decode('unicode_escape')
        except:
            return unicode_str
    
    # 匹配\uXXXX格式的Unicode转义
    unicode_pattern = r'\\u[0-9a-fA-F]{4}'
    text = re.sub(unicode_pattern, replace_unicode, text)
    
    return text

def parse_js_object_to_json(js_obj_str):
    """
    将JavaScript对象字符串转换为JSON格式，处理混淆的变量名
    """
    # 首先处理Unicode转义
    js_obj_str = convert_unicode_escapes(js_obj_str)
    
    try:
        # 尝试直接解析为JSON
        try:
            return json.loads(js_obj_str)
        except json.JSONDecodeError:
            pass
        
        # 处理JavaScript对象格式
        # 1. 添加引号到属性名（包括单字母变量）
        js_obj_str = re.sub(r'([{,\[]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'\1"\2":', js_obj_str)
        
        # 2. 处理未引用的字符串值，但要小心数字和布尔值
        # 匹配单字母或多字母变量作为值（排除数字、true、false、null）
        def replace_value(m):
            value = m.group(1)
            if value not in ['true', 'false', 'null'] and not value.isdigit():
                return f': "{value}"'
            return m.group(0)
        
        js_obj_str = re.sub(r':\s*([a-zA-Z_$][a-zA-Z0-9_$]*)(?=\s*[,}\]])', replace_value, js_obj_str)
        
        # 3. 处理数组中的未引用变量
        def replace_array_value(m):
            prefix = m.group(1)
            value = m.group(2)
            if value not in ['true', 'false', 'null'] and not value.isdigit():
                return f'{prefix}"{value}"'
            return m.group(0)
        
        js_obj_str = re.sub(r'(\[\s*|,\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)(?=\s*[,\]])', replace_array_value, js_obj_str)
        
        # 处理单引号字符串
        js_obj_str = re.sub(r"'([^']*)'(?=\s*[,}\]])", r'"\1"', js_obj_str)
        
        # 处理undefined值
        js_obj_str = re.sub(r'\bundefined\b', 'null', js_obj_str)
        
        # 再次尝试解析
        return json.loads(js_obj_str)
        
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"错误位置附近的内容: {js_obj_str[max(0, e.pos-50):e.pos+50]}")
        return None
    except Exception as e:
        print(f"解析JavaScript对象时出错: {e}")
        print(f"错误位置附近的内容: {js_obj_str[:200]}...")
        return None

def convert_team_detail_json():
    """
    转换team_detail_.json文件中的raw_content
    """
    input_file = "team_detail_.json"
    output_file = "team_detail_converted.json"
    
    try:
        # 读取原始JSON文件
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 获取raw_content字符串
        raw_content = data.get('team_detail', {}).get('raw_content', '')
        
        if not raw_content:
            print("未找到raw_content字段")
            return
        
        print(f"原始raw_content长度: {len(raw_content)}")
        
        # 解析JavaScript对象为JSON
        parsed_content = parse_js_object_to_json(raw_content)
        
        if parsed_content is None:
            print("解析失败，尝试保存原始内容以供调试")
            with open("raw_content_debug.txt", 'w', encoding='utf-8') as f:
                f.write(raw_content)
            return
        
        # 更新数据结构
        data['team_detail']['parsed_content'] = parsed_content
        data['team_detail']['conversion_time'] = datetime.now().isoformat()
        
        # 保存转换后的JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"转换完成！结果保存到: {output_file}")
        print(f"解析后的数据包含以下主要字段:")
        if isinstance(parsed_content, dict):
            for key in parsed_content.keys():
                print(f"  - {key}")
        
    except FileNotFoundError:
        print(f"文件 {input_file} 不存在")
    except json.JSONDecodeError as e:
        print(f"JSON文件格式错误: {e}")
    except Exception as e:
        print(f"转换过程中发生错误: {e}")

if __name__ == "__main__":
    convert_team_detail_json()