"""
PDF Compression Parameter Presets - Three compression levels

Ghostscript custom parameters, no presets used, precise control over compression rate and quality balance.
Key parameter notes:
- QFactor: 0.40≈JPEG85-90(near-lossless), 0.76≈JPEG50-60(sweet spot), 0.90≈JPEG35-40(acceptable)
- HSamples/VSamples: [2 1 1 2] for 4:2:0 chroma subsampling, extra 25% savings
- Downsampling algorithm: Bicubic smoothest, Average faster
"""


# Low compression (high quality priority) - visually lossless
# Expected compression 50-70%, suitable for printing or detailed viewing
LOW_COMPRESSION = {
    "name": "Low Compression (High Quality)",
    "description": "Visually lossless, suitable for printing or detailed viewing",

    # Base settings
    "compatibility_level": "1.7",

    # Color image downsampling - high resolution preserved
    "DownsampleColorImages": True,
    "ColorImageResolution": 200,
    "ColorImageDownsampleType": "/Bicubic",
    "ColorImageDownsampleThreshold": 1.5,

    # Grayscale images
    "DownsampleGrayImages": True,
    "GrayImageResolution": 200,
    "GrayImageDownsampleType": "/Bicubic",
    "GrayImageDownsampleThreshold": 1.5,

    # Monochrome images - keep high resolution (text clarity)
    "DownsampleMonoImages": True,
    "MonoImageResolution": 600,
    "MonoImageDownsampleType": "/Subsample",

    # JPEG compression quality - QFactor 0.40 ≈ JPEG quality 85-90
    "ColorImageQFactor": 0.40,
    "ColorHSamples": "[1 1 1 1]",
    "ColorVSamples": "[1 1 1 1]",
    "GrayImageQFactor": 0.40,
    "GrayHSamples": "[1 1 1 1]",
    "GrayVSamples": "[1 1 1 1]",

    # Color space - no conversion, preserve original
    "ColorConversionStrategy": "/LeaveColorUnchanged",

    # Fonts
    "EmbedAllFonts": True,
    "SubsetFonts": True,
    "CompressFonts": True,

    # Optimization
    "DetectDuplicateImages": True,
    "AutoFilterColorImages": True,
    "AutoFilterGrayImages": True,
}


# Medium compression (balanced) - recommended, target 20MB -> 2MB
# Expected compression 80-90%, daily sharing, email attachments
MEDIUM_COMPRESSION = {
    "name": "Medium Compression (Recommended)",
    "description": "Excellent visual quality with significantly reduced file size",

    # Base settings
    "compatibility_level": "1.5",

    # Color image downsampling - balanced resolution
    "DownsampleColorImages": True,
    "ColorImageResolution": 150,
    "ColorImageDownsampleType": "/Bicubic",
    "ColorImageDownsampleThreshold": 1.1,

    # Grayscale images
    "DownsampleGrayImages": True,
    "GrayImageResolution": 150,
    "GrayImageDownsampleType": "/Bicubic",
    "GrayImageDownsampleThreshold": 1.1,

    # Monochrome images - moderate downsampling
    "DownsampleMonoImages": True,
    "MonoImageResolution": 300,
    "MonoImageDownsampleType": "/Subsample",

    # JPEG compression quality - QFactor 0.76 ≈ JPEG quality 50-60 (sweet spot)
    "ColorImageQFactor": 0.76,
    "ColorHSamples": "[2 1 1 2]",
    "ColorVSamples": "[2 1 1 2]",
    "GrayImageQFactor": 0.76,
    "GrayHSamples": "[2 1 1 2]",
    "GrayVSamples": "[2 1 1 2]",

    # Color space - convert to RGB (CMYK to RGB saves 25% image data)
    "ColorConversionStrategy": "/RGB",

    # Fonts
    "EmbedAllFonts": True,
    "SubsetFonts": True,
    "CompressFonts": True,

    # Optimization
    "DetectDuplicateImages": True,
    "AutoFilterColorImages": True,
    "AutoFilterGrayImages": True,

    # Extra optimization
    "Optimize": True,
    "PreserveHalftoneInfo": False,
    "PreserveOverprintSettings": False,
    "TransferFunctionInfo": "/Apply",
    "UCRandBGInfo": "/Remove",
}


# High compression (maximum compression) - minimize file size
# Expected compression 85-95%, maintain readability
HIGH_COMPRESSION = {
    "name": "High Compression (Smallest Size)",
    "description": "Minimize file size while maintaining readability",

    # Base settings
    "compatibility_level": "1.5",

    # Color image downsampling - more aggressive
    "DownsampleColorImages": True,
    "ColorImageResolution": 100,
    "ColorImageDownsampleType": "/Average",
    "ColorImageDownsampleThreshold": 1.0,

    # Grayscale images
    "DownsampleGrayImages": True,
    "GrayImageResolution": 100,
    "GrayImageDownsampleType": "/Average",
    "GrayImageDownsampleThreshold": 1.0,

    # Monochrome images
    "DownsampleMonoImages": True,
    "MonoImageResolution": 300,
    "MonoImageDownsampleType": "/Subsample",
    "MonoImageDownsampleThreshold": 1.0,

    # JPEG compression quality - QFactor 0.90 ≈ JPEG quality 35-40
    "ColorImageQFactor": 0.90,
    "ColorHSamples": "[2 1 1 2]",
    "ColorVSamples": "[2 1 1 2]",
    "GrayImageQFactor": 0.90,
    "GrayHSamples": "[2 1 1 2]",
    "GrayVSamples": "[2 1 1 2]",

    # Color space - convert to RGB
    "ColorConversionStrategy": "/RGB",

    # Fonts - minimize font embedding
    "EmbedAllFonts": False,
    "SubsetFonts": True,
    "CompressFonts": True,

    # Full optimization
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


# Compression level mapping
COMPRESSION_PROFILES = {
    "low": LOW_COMPRESSION,
    "medium": MEDIUM_COMPRESSION,
    "high": HIGH_COMPRESSION,
}


def get_profile(level: str) -> dict:
    """Get compression parameters for specified level"""
    if level not in COMPRESSION_PROFILES:
        raise ValueError(f"Unknown compression level: {level}, available: {list(COMPRESSION_PROFILES.keys())}")
    return COMPRESSION_PROFILES[level]
