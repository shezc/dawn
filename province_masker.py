"""
中国省份/城市信息脱敏与还原工具

功能：
1. 将文本中的省份、城市相关信息进行脱敏（包括各种组合形式）
2. 提供还原方法，以便在 LLM 处理后恢复原始信息

示例：
- "陕西到山西的铁路" -> "陕山高铁" 中的 "陕山" 会被脱敏
- "京沪高铁" 中的 "京沪" 会被脱敏
- "渝昆高铁" 中的 "渝昆" 会被脱敏
"""

import re
import uuid
import json
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass, field


@dataclass
class MaskResult:
    """脱敏结果"""
    masked_text: str  # 脱敏后的文本
    mapping: Dict[str, str] = field(default_factory=dict)  # 占位符 -> 原始内容的映射
    
    def restore(self) -> str:
        """还原脱敏后的文本"""
        result = self.masked_text
        # 按占位符长度降序排序，避免短占位符替换长占位符的一部分
        for placeholder, original in sorted(self.mapping.items(), key=lambda x: -len(x[0])):
            result = result.replace(placeholder, original)
        return result
    
    def to_dict(self) -> dict:
        """转换为字典，方便序列化"""
        return {
            "masked_text": self.masked_text,
            "mapping": self.mapping
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MaskResult':
        """从字典创建对象"""
        return cls(
            masked_text=data["masked_text"],
            mapping=data.get("mapping", {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MaskResult':
        """从 JSON 字符串创建对象"""
        return cls.from_dict(json.loads(json_str))


class ProvinceMasker:
    """省份/城市信息脱敏器"""
    
    # 中国省份/直辖市/自治区/特别行政区信息
    # 格式: (全称, 简称, 单字简称列表)
    PROVINCE_DATA = [
        # 直辖市
        ("北京市", "北京", ["京"]),
        ("天津市", "天津", ["津"]),
        ("上海市", "上海", ["沪", "申"]),
        ("重庆市", "重庆", ["渝"]),
        
        # 省份
        ("河北省", "河北", ["冀"]),
        ("山西省", "山西", ["晋"]),
        ("辽宁省", "辽宁", ["辽"]),
        ("吉林省", "吉林", ["吉"]),
        ("黑龙江省", "黑龙江", ["黑"]),
        ("江苏省", "江苏", ["苏"]),
        ("浙江省", "浙江", ["浙"]),
        ("安徽省", "安徽", ["皖"]),
        ("福建省", "福建", ["闽"]),
        ("江西省", "江西", ["赣"]),
        ("山东省", "山东", ["鲁"]),
        ("河南省", "河南", ["豫"]),
        ("湖北省", "湖北", ["鄂"]),
        ("湖南省", "湖南", ["湘"]),
        ("广东省", "广东", ["粤"]),
        ("海南省", "海南", ["琼"]),
        ("四川省", "四川", ["川", "蜀"]),
        ("贵州省", "贵州", ["贵", "黔"]),
        ("云南省", "云南", ["云", "滇"]),
        ("陕西省", "陕西", ["陕", "秦"]),
        ("甘肃省", "甘肃", ["甘", "陇"]),
        ("青海省", "青海", ["青"]),
        ("台湾省", "台湾", ["台"]),
        
        # 自治区
        ("内蒙古自治区", "内蒙古", ["蒙"]),
        ("广西壮族自治区", "广西", ["桂"]),
        ("西藏自治区", "西藏", ["藏"]),
        ("宁夏回族自治区", "宁夏", ["宁"]),
        ("新疆维吾尔自治区", "新疆", ["新"]),
        
        # 特别行政区
        ("香港特别行政区", "香港", ["港"]),
        ("澳门特别行政区", "澳门", ["澳"]),
    ]
    
    # 主要城市简称 (城市名, 简称列表)
    # 只包含常用于交通线路命名的城市简称
    CITY_DATA = [
        ("昆明", ["昆"]),
        ("南京", ["宁"]),  # 注意：宁也是宁夏的简称
        ("杭州", ["杭"]),
        ("深圳", ["深"]),
        ("广州", ["穗"]),
        ("成都", ["蓉", "成"]),
        ("武汉", ["汉", "武"]),
        ("西安", ["西"]),
        ("南宁", ["邕"]),
        ("哈尔滨", ["哈"]),
        ("长沙", ["长"]),
        ("南昌", ["洪"]),
        ("福州", ["榕"]),
        ("兰州", ["兰"]),
        ("太原", ["并"]),
        ("济南", ["济"]),
        ("石家庄", ["石"]),
        ("郑州", ["郑"]),
        ("合肥", ["合"]),
        ("厦门", ["厦", "鹭"]),
        ("大连", ["连", "大"]),
        ("九江", ["九"]),
        ("贵阳", ["筑"]),
        ("拉萨", ["拉"]),
        ("乌鲁木齐", ["乌"]),
        ("呼和浩特", ["呼"]),
        ("银川", ["银"]),
        ("徐州", ["徐"]),
        ("包头", ["包"]),
        ("襄阳", ["襄"]),
        ("宜昌", ["宜"]),
        ("洛阳", ["洛"]),
        ("无锡", ["锡"]),
        ("苏州", ["苏"]),
        ("温州", ["温"]),
        ("宁波", ["甬"]),
        ("泉州", ["泉"]),
        ("潍坊", ["潍"]),
        ("柳州", ["柳"]),
        ("桂林", ["桂"]),
        ("曲靖", ["曲"]),
        ("遵义", ["遵"]),
        ("绵阳", ["绵"]),
        ("宝鸡", ["宝"]),
        ("咸阳", ["咸"]),
        ("榆林", ["榆"]),
        ("沈阳", ["沈"]),
        ("长春", ["春"]),
    ]
    
    # 高歧义字符：这些字符在非地理上下文中也很常见，需要特殊处理
    # 只有在特定上下文（如后跟"高铁"、"铁路"等）时才脱敏
    HIGH_AMBIGUITY_CHARS = {
        "南",  # 南方、南边
        "北",  # 北方、北边
        "东",  # 东方、东边
        "西",  # 西方、西边、西安中的西（但西安作为整体会被匹配）
        "中",  # 中国、中间
        "大",  # 大的
        "长",  # 长的
        "新",  # 新的（但新疆的简称会被处理）
        "海",  # 大海
        "山",  # 山脉（但山西、山东会被处理）
        "三",  # 数字三
        "青",  # 青色（但青海会被处理）
    }
    
    # 特殊的地理区域名称（需要整体匹配）
    SPECIAL_REGIONS = [
        "长三角",
        "珠三角",
        "环渤海",
        "大湾区",
        "成渝",
        "京津冀",
        "长株潭",
    ]
    
    def __init__(self, 
                 placeholder_prefix: str = "[PROV_", 
                 placeholder_suffix: str = "]",
                 include_cities: bool = True,
                 include_special_regions: bool = True,
                 strict_mode: bool = True):
        """
        初始化脱敏器
        
        Args:
            placeholder_prefix: 占位符前缀
            placeholder_suffix: 占位符后缀
            include_cities: 是否包含城市简称
            include_special_regions: 是否包含特殊地理区域名称
            strict_mode: 严格模式，减少误匹配（排除高歧义字符的组合）
        """
        self.placeholder_prefix = placeholder_prefix
        self.placeholder_suffix = placeholder_suffix
        self.include_cities = include_cities
        self.include_special_regions = include_special_regions
        self.strict_mode = strict_mode
        
        # 构建各种省份/城市表示形式
        self._build_patterns()
    
    def _build_patterns(self):
        """构建匹配模式"""
        # 所有省份的全称
        self.full_names: Set[str] = set()
        # 所有省份的简称（如"北京"、"山西"）
        self.short_names: Set[str] = set()
        # 所有省份的单字简称（如"京"、"沪"）
        self.province_single_chars: Set[str] = set()
        # 单字简称到省份/城市的映射
        self.char_to_location: Dict[str, str] = {}
        
        for full_name, short_name, single_chars in self.PROVINCE_DATA:
            self.full_names.add(full_name)
            self.short_names.add(short_name)
            for char in single_chars:
                self.province_single_chars.add(char)
                self.char_to_location[char] = short_name
        
        # 提取省份名称中的首字（如"陕"来自"陕西"）
        self.province_first_chars: Set[str] = set()
        for _, short_name, _ in self.PROVINCE_DATA:
            if len(short_name) >= 1:
                self.province_first_chars.add(short_name[0])
        
        # 添加城市简称
        self.city_names: Set[str] = set()
        self.city_chars: Set[str] = set()
        
        if self.include_cities:
            for city_name, single_chars in self.CITY_DATA:
                self.city_names.add(city_name)
                for char in single_chars:
                    self.city_chars.add(char)
                    if char not in self.char_to_location:
                        self.char_to_location[char] = city_name
        
        # 低歧义的地理字符（排除高歧义字符）
        if self.strict_mode:
            self.low_ambiguity_chars = (
                (self.province_single_chars | self.province_first_chars | self.city_chars) 
                - self.HIGH_AMBIGUITY_CHARS
            )
        else:
            self.low_ambiguity_chars = (
                self.province_single_chars | self.province_first_chars | self.city_chars
            )
        
        # 所有地理相关字符（包含高歧义字符，用于上下文匹配）
        self.all_geo_chars: Set[str] = (
            self.province_single_chars | self.province_first_chars | self.city_chars
        )
        
        # 构建字符组合
        self._build_char_combinations()
    
    def _build_char_combinations(self):
        """构建省份/城市字符的组合"""
        # 使用低歧义字符构建组合
        low_ambig_chars = list(self.low_ambiguity_chars)
        
        # 双字组合（如"京沪"、"陕山"、"渝昆"等）
        # 至少一个字符是低歧义的
        self.geo_pairs: Set[str] = set()
        all_chars = list(self.all_geo_chars)
        
        for c1 in all_chars:
            for c2 in all_chars:
                if c1 != c2:
                    # 在严格模式下，至少需要一个低歧义字符
                    if self.strict_mode:
                        if c1 in self.low_ambiguity_chars or c2 in self.low_ambiguity_chars:
                            self.geo_pairs.add(c1 + c2)
                    else:
                        self.geo_pairs.add(c1 + c2)
        
        # 三字组合（如"京津冀"、"沪宁杭"等）
        self.geo_triples: Set[str] = set()
        for c1 in all_chars:
            for c2 in all_chars:
                for c3 in all_chars:
                    if len(set([c1, c2, c3])) == 3:
                        # 在严格模式下，至少需要两个低歧义字符
                        if self.strict_mode:
                            low_count = sum(1 for c in [c1, c2, c3] if c in self.low_ambiguity_chars)
                            if low_count >= 2:
                                self.geo_triples.add(c1 + c2 + c3)
                        else:
                            self.geo_triples.add(c1 + c2 + c3)
    
    def _generate_placeholder(self) -> str:
        """生成唯一的占位符"""
        short_uuid = uuid.uuid4().hex[:8].upper()
        return f"{self.placeholder_prefix}{short_uuid}{self.placeholder_suffix}"
    
    def _find_geo_matches(self, text: str) -> List[Tuple[int, int, str]]:
        """
        查找文本中所有地理相关的内容
        
        Returns:
            List of (start_pos, end_pos, matched_text)
        """
        matches = []
        
        # 0. 首先匹配特殊地理区域名称（优先级最高）
        if self.include_special_regions:
            for region in sorted(self.SPECIAL_REGIONS, key=len, reverse=True):
                for m in re.finditer(re.escape(region), text):
                    matches.append((m.start(), m.end(), m.group()))
        
        # 1. 匹配省份全称（如"陕西省"、"北京市"）
        for full_name in sorted(self.full_names, key=len, reverse=True):
            for m in re.finditer(re.escape(full_name), text):
                matches.append((m.start(), m.end(), m.group()))
        
        # 2. 匹配省份简称（如"陕西"、"北京"）
        for short_name in sorted(self.short_names, key=len, reverse=True):
            for m in re.finditer(re.escape(short_name), text):
                matches.append((m.start(), m.end(), m.group()))
        
        # 3. 匹配城市名称（如"昆明"、"深圳"）
        if self.include_cities:
            for city_name in sorted(self.city_names, key=len, reverse=True):
                for m in re.finditer(re.escape(city_name), text):
                    matches.append((m.start(), m.end(), m.group()))
        
        # 4. 匹配三字组合（如"京津冀"、"沪宁杭"）
        for triple in self.geo_triples:
            for m in re.finditer(re.escape(triple), text):
                matches.append((m.start(), m.end(), m.group()))
        
        # 5. 匹配双字组合（如"京沪"、"陕山"、"渝昆"等）
        for pair in self.geo_pairs:
            for m in re.finditer(re.escape(pair), text):
                matches.append((m.start(), m.end(), m.group()))
        
        # 去重并按位置排序
        matches = list(set(matches))
        matches.sort(key=lambda x: (x[0], -x[1]))
        
        return matches
    
    def _merge_overlapping_matches(self, matches: List[Tuple[int, int, str]]) -> List[Tuple[int, int, str]]:
        """合并重叠的匹配结果，优先保留较长的匹配"""
        if not matches:
            return []
        
        # 按起始位置排序，相同位置优先选择更长的
        matches = sorted(matches, key=lambda x: (x[0], -(x[1] - x[0])))
        
        merged = []
        current_end = -1
        
        for start, end, text in matches:
            if start >= current_end:
                merged.append((start, end, text))
                current_end = end
        
        return merged
    
    def mask(self, text: str, mask_single_chars: bool = False) -> MaskResult:
        """
        对文本进行地理信息脱敏
        
        Args:
            text: 原始文本
            mask_single_chars: 是否脱敏单独出现的简称字符（如独立的"京"）
                              默认 False，因为这些字符可能有其他含义
        
        Returns:
            MaskResult 对象，包含脱敏后的文本和映射关系
        """
        # 查找所有地理相关内容
        matches = self._find_geo_matches(text)
        
        # 如果需要脱敏单独的字符（只脱敏低歧义字符）
        if mask_single_chars:
            for char in self.low_ambiguity_chars:
                for m in re.finditer(re.escape(char), text):
                    matches.append((m.start(), m.end(), m.group()))
        
        # 合并重叠的匹配
        matches = self._merge_overlapping_matches(matches)
        
        if not matches:
            return MaskResult(masked_text=text, mapping={})
        
        # 构建脱敏后的文本
        mapping = {}
        result_parts = []
        last_end = 0
        
        for start, end, matched_text in matches:
            # 添加匹配之前的部分
            result_parts.append(text[last_end:start])
            
            # 生成占位符并添加
            placeholder = self._generate_placeholder()
            mapping[placeholder] = matched_text
            result_parts.append(placeholder)
            
            last_end = end
        
        # 添加最后剩余的部分
        result_parts.append(text[last_end:])
        
        masked_text = ''.join(result_parts)
        return MaskResult(masked_text=masked_text, mapping=mapping)
    
    def restore(self, masked_text: str, mapping: Dict[str, str]) -> str:
        """
        还原脱敏后的文本
        
        Args:
            masked_text: 脱敏后的文本
            mapping: 占位符到原始内容的映射
        
        Returns:
            还原后的原始文本
        """
        result = masked_text
        for placeholder, original in sorted(mapping.items(), key=lambda x: -len(x[0])):
            result = result.replace(placeholder, original)
        return result
    
    def get_location_info(self, char: str) -> str:
        """
        获取简称字符对应的地理信息
        
        Args:
            char: 简称字符
        
        Returns:
            对应的省份/城市名称，如果找不到返回空字符串
        """
        return self.char_to_location.get(char, "")


class AdvancedProvinceMasker(ProvinceMasker):
    """高级省份/城市脱敏器，支持更多自定义选项和上下文感知"""
    
    # 常见的地理组合后缀词
    SUFFIX_KEYWORDS = [
        "高铁", "铁路", "高速", "公路", "航线", "航班", 
        "线", "道", "路", "段", "区间", "通道",
        "经济带", "城市群", "合作区", "示范区", "经济圈",
        "一体化", "都市圈", "协作区", "双城",
    ]
    
    def __init__(self, 
                 placeholder_prefix: str = "[PROV_", 
                 placeholder_suffix: str = "]",
                 include_cities: bool = True,
                 include_special_regions: bool = True,
                 strict_mode: bool = True,
                 custom_keywords: List[str] = None,
                 custom_regions: List[str] = None):
        """
        初始化高级脱敏器
        
        Args:
            placeholder_prefix: 占位符前缀
            placeholder_suffix: 占位符后缀
            include_cities: 是否包含城市简称
            include_special_regions: 是否包含特殊地理区域名称
            strict_mode: 严格模式，减少误匹配
            custom_keywords: 自定义的后缀关键词列表
            custom_regions: 自定义的特殊地理区域名称列表
        """
        super().__init__(
            placeholder_prefix, 
            placeholder_suffix, 
            include_cities, 
            include_special_regions,
            strict_mode
        )
        
        if custom_keywords:
            self.SUFFIX_KEYWORDS = list(set(self.SUFFIX_KEYWORDS + custom_keywords))
        
        if custom_regions:
            self.SPECIAL_REGIONS = list(set(self.SPECIAL_REGIONS + custom_regions))
    
    def mask_with_context(self, text: str) -> MaskResult:
        """
        基于上下文的智能脱敏
        
        会检测省份/城市字符后跟关键词的情况
        例如："京沪高铁" 会被整体识别
        """
        # 首先进行标准脱敏
        matches = self._find_geo_matches(text)
        
        # 额外匹配：地理字符 + 后缀关键词 的模式
        # 这里使用所有地理字符（包括高歧义字符），因为有上下文支持
        all_chars_str = ''.join(self.all_geo_chars)
        
        for suffix in self.SUFFIX_KEYWORDS:
            # 匹配模式：一个或多个地理字符 + 后缀关键词
            pattern = f"[{re.escape(all_chars_str)}]{{1,5}}{re.escape(suffix)}"
            for m in re.finditer(pattern, text):
                matched = m.group()
                province_part = matched[:-len(suffix)]
                if len(province_part) >= 1:
                    # 检查是否至少包含一个低歧义的地理字符
                    has_low_ambig = any(c in self.low_ambiguity_chars for c in province_part)
                    if has_low_ambig:
                        matches.append((m.start(), m.start() + len(province_part), province_part))
        
        # 合并所有匹配
        matches = self._merge_overlapping_matches(matches)
        
        if not matches:
            return MaskResult(masked_text=text, mapping={})
        
        # 构建脱敏后的文本
        mapping = {}
        result_parts = []
        last_end = 0
        
        for start, end, matched_text in matches:
            result_parts.append(text[last_end:start])
            placeholder = self._generate_placeholder()
            mapping[placeholder] = matched_text
            result_parts.append(placeholder)
            last_end = end
        
        result_parts.append(text[last_end:])
        masked_text = ''.join(result_parts)
        
        return MaskResult(masked_text=masked_text, mapping=mapping)


def demo():
    """演示脱敏功能"""
    masker = AdvancedProvinceMasker()
    
    test_cases = [
        "陕山高铁连接陕西和山西两省",
        "京沪高铁是中国最繁忙的高铁线路",
        "从北京到上海可以乘坐京沪高铁",
        "渝昆高铁将重庆和云南昆明连接起来",
        "广深港高铁连接广东深圳和香港",
        "川渝经济带发展迅速",
        "沪宁杭城市群是长三角的核心",
        "京九铁路贯穿南北",  # "南北"不应该被脱敏
        "京津冀一体化发展战略",
        "我住在陕西省西安市",
        "请问从山西太原到陕西西安怎么走？",
        "成渝双城经济圈建设加速推进",
        "粤港澳大湾区发展规划",
        "长三角一体化示范区",
        "武广高铁是武汉到广州的高速铁路",
        "沪昆高铁贯穿东西",  # "东西"不应该被脱敏
        "兰新高铁连接兰州和乌鲁木齐",
        "这是一个向北走的路线",  # "北"不应该被脱敏
        "他住在城市的西边",  # "西"不应该被脱敏
    ]
    
    print("=" * 70)
    print("省份/城市信息脱敏演示")
    print("=" * 70)
    
    for text in test_cases:
        print(f"\n原文: {text}")
        
        # 使用上下文感知的脱敏
        result = masker.mask_with_context(text)
        print(f"脱敏: {result.masked_text}")
        print(f"映射: {result.mapping}")
        
        # 还原
        restored = result.restore()
        print(f"还原: {restored}")
        
        # 验证还原是否正确
        assert restored == text, f"还原失败！原文：{text}，还原：{restored}"
    
    print("\n" + "=" * 70)
    print("所有测试用例通过！")
    print("=" * 70)
    
    # 演示序列化
    print("\n" + "=" * 70)
    print("序列化演示（用于传递给 LLM）")
    print("=" * 70)
    
    sample_text = "京沪高铁是连接北京和上海的高速铁路"
    result = masker.mask_with_context(sample_text)
    
    print(f"\n原文: {sample_text}")
    print(f"\n脱敏后的 JSON（可传给 LLM）:")
    print(result.to_json())
    
    # 从 JSON 还原
    json_str = result.to_json()
    restored_result = MaskResult.from_json(json_str)
    print(f"\n从 JSON 还原: {restored_result.restore()}")


def usage_example():
    """使用示例"""
    print("\n" + "=" * 70)
    print("使用示例")
    print("=" * 70)
    
    # 创建脱敏器
    masker = AdvancedProvinceMasker()
    
    # 原始文本
    original_text = "京沪高铁连接北京和上海，是中国最繁忙的铁路线"
    
    # 1. 脱敏
    result = masker.mask_with_context(original_text)
    masked_text = result.masked_text
    mapping = result.mapping
    
    print(f"\n1. 原始文本: {original_text}")
    print(f"2. 脱敏文本: {masked_text}")
    print(f"3. 映射关系: {mapping}")
    
    # 2. 将脱敏后的文本发送给 LLM 处理
    # （这里模拟 LLM 返回的结果）
    llm_response = f"根据分析，{masked_text.replace('高铁', '高速铁路')}，日均客流量超过50万人次。"
    print(f"4. LLM 响应: {llm_response}")
    
    # 3. 还原 LLM 响应中的占位符
    restored_response = masker.restore(llm_response, mapping)
    print(f"5. 还原响应: {restored_response}")
    
    # 演示完整的 LLM 调用流程
    print("\n" + "-" * 70)
    print("完整的 LLM 调用流程示例代码:")
    print("-" * 70)
    print("""
from province_masker import AdvancedProvinceMasker, MaskResult

# 1. 创建脱敏器
masker = AdvancedProvinceMasker()

# 2. 用户输入
user_input = "请介绍京沪高铁的基本情况"

# 3. 脱敏
mask_result = masker.mask_with_context(user_input)
print(f"发送给 LLM 的文本: {mask_result.masked_text}")

# 4. 调用 LLM（伪代码）
# llm_response = call_llm(mask_result.masked_text)

# 5. 还原 LLM 响应
# restored = mask_result.restore()  # 如果 LLM 返回了包含占位符的文本
# 或者使用：
# restored = masker.restore(llm_response, mask_result.mapping)
""")


if __name__ == "__main__":
    demo()
    usage_example()
