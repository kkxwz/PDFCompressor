"""
PDF 压缩参数预设 - 三档压缩配置

Ghostscript 自定义参数，不使用预设，精确控制压缩率与质量平衡。
关键参数说明：
- QFactor: 0.40≈JPEG85-90(近无损), 0.76≈JPEG50-60(甜点), 0.90≈JPEG35-40(可接受)
- HSamples/VSamples: [2 1 1 2] 做 4:2:0 色度子采样，额外节省25%
- 降采样算法: Bicubic 最平滑，Average 更快
"""


# 低压缩（高质量优先）- 视觉无损
# 预期压缩率 50-70%，适合打印或精细查看
LOW_COMPRESSION = {
    "name": "低压缩（高质量）",
    "description": "视觉无损，适合打印或精细查看",

    # 基础设置
    "compatibility_level": "1.7",

    # 彩色图像降采样 - 高分辨率保持
    "DownsampleColorImages": True,
    "ColorImageResolution": 200,
    "ColorImageDownsampleType": "/Bicubic",
    "ColorImageDownsampleThreshold": 1.5,

    # 灰度图像
    "DownsampleGrayImages": True,
    "GrayImageResolution": 200,
    "GrayImageDownsampleType": "/Bicubic",
    "GrayImageDownsampleThreshold": 1.5,

    # 黑白图像 - 保持高分辨率（文字清晰）
    "DownsampleMonoImages": True,
    "MonoImageResolution": 600,
    "MonoImageDownsampleType": "/Subsample",

    # JPEG 压缩质量 - QFactor 0.40 ≈ JPEG quality 85-90
    "ColorImageQFactor": 0.40,
    "ColorHSamples": "[1 1 1 1]",
    "ColorVSamples": "[1 1 1 1]",
    "GrayImageQFactor": 0.40,
    "GrayHSamples": "[1 1 1 1]",
    "GrayVSamples": "[1 1 1 1]",

    # 颜色空间 - 不转换，保持原色
    "ColorConversionStrategy": "/LeaveColorUnchanged",

    # 字体
    "EmbedAllFonts": True,
    "SubsetFonts": True,
    "CompressFonts": True,

    # 优化
    "DetectDuplicateImages": True,
    "AutoFilterColorImages": True,
    "AutoFilterGrayImages": True,
}


# 中压缩（平衡档）- 推荐，目标 20MB -> 2MB
# 预期压缩率 80-90%，日常分享、邮件附件
MEDIUM_COMPRESSION = {
    "name": "中压缩（推荐）",
    "description": "视觉质量优秀，文件大小显著减小",

    # 基础设置
    "compatibility_level": "1.5",

    # 彩色图像降采样 - 平衡分辨率
    "DownsampleColorImages": True,
    "ColorImageResolution": 150,
    "ColorImageDownsampleType": "/Bicubic",
    "ColorImageDownsampleThreshold": 1.1,

    # 灰度图像
    "DownsampleGrayImages": True,
    "GrayImageResolution": 150,
    "GrayImageDownsampleType": "/Bicubic",
    "GrayImageDownsampleThreshold": 1.1,

    # 黑白图像 - 适度降采样
    "DownsampleMonoImages": True,
    "MonoImageResolution": 300,
    "MonoImageDownsampleType": "/Subsample",

    # JPEG 压缩质量 - QFactor 0.76 ≈ JPEG quality 50-60（甜点）
    "ColorImageQFactor": 0.76,
    "ColorHSamples": "[2 1 1 2]",
    "ColorVSamples": "[2 1 1 2]",
    "GrayImageQFactor": 0.76,
    "GrayHSamples": "[2 1 1 2]",
    "GrayVSamples": "[2 1 1 2]",

    # 颜色空间 - 转 RGB（CMYK 转 RGB 可节省 25% 图像数据）
    "ColorConversionStrategy": "/RGB",

    # 字体
    "EmbedAllFonts": True,
    "SubsetFonts": True,
    "CompressFonts": True,

    # 优化
    "DetectDuplicateImages": True,
    "AutoFilterColorImages": True,
    "AutoFilterGrayImages": True,

    # 额外优化
    "Optimize": True,
    "PreserveHalftoneInfo": False,
    "PreserveOverprintSettings": False,
    "TransferFunctionInfo": "/Apply",
    "UCRandBGInfo": "/Remove",
}


# 高压缩（极致压缩）- 文件大小最小化
# 预期压缩率 85-95%，保持可读性
HIGH_COMPRESSION = {
    "name": "高压缩（最小体积）",
    "description": "文件大小最小化，保持可读性",

    # 基础设置
    "compatibility_level": "1.5",

    # 彩色图像降采样 - 更激进
    "DownsampleColorImages": True,
    "ColorImageResolution": 100,
    "ColorImageDownsampleType": "/Average",
    "ColorImageDownsampleThreshold": 1.0,

    # 灰度图像
    "DownsampleGrayImages": True,
    "GrayImageResolution": 100,
    "GrayImageDownsampleType": "/Average",
    "GrayImageDownsampleThreshold": 1.0,

    # 黑白图像
    "DownsampleMonoImages": True,
    "MonoImageResolution": 300,
    "MonoImageDownsampleType": "/Subsample",
    "MonoImageDownsampleThreshold": 1.0,

    # JPEG 压缩质量 - QFactor 0.90 ≈ JPEG quality 35-40
    "ColorImageQFactor": 0.90,
    "ColorHSamples": "[2 1 1 2]",
    "ColorVSamples": "[2 1 1 2]",
    "GrayImageQFactor": 0.90,
    "GrayHSamples": "[2 1 1 2]",
    "GrayVSamples": "[2 1 1 2]",

    # 颜色空间 - 转 RGB
    "ColorConversionStrategy": "/RGB",

    # 字体 - 最小化字体嵌入
    "EmbedAllFonts": False,
    "SubsetFonts": True,
    "CompressFonts": True,

    # 全面优化
    "DetectDuplicateImages": True,
    "AutoFilterColorImages": True,
    "AutoFilterGrayImages": True,
    "Optimize": True,
    "PreserveHalftoneInfo": False,
    "PreserveOverprintSettings": False,
    "PreserveMarkedContent": False,
    "TransferFunctionInfo": "/Apply",
    "UCRandBGInfo": "/Remove",
}


# 压缩级别映射
COMPRESSION_PROFILES = {
    "low": LOW_COMPRESSION,
    "medium": MEDIUM_COMPRESSION,
    "high": HIGH_COMPRESSION,
}


def get_profile(level: str) -> dict:
    """获取指定级别的压缩参数"""
    if level not in COMPRESSION_PROFILES:
        raise ValueError(f"未知的压缩级别: {level}，可选: {list(COMPRESSION_PROFILES.keys())}")
    return COMPRESSION_PROFILES[level]
