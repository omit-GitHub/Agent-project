# -*- coding: utf-8 -*-
"""Candidates 子包 — 候选生成、融合、指纹。"""
from .schemas import PixelBBox, UiCandidate, CandidateMap, ProviderResult
from .fingerprint import ScreenIdentity, FingerprintBuilder, DynamicRegionMasker

__all__ = [
    "PixelBBox",
    "UiCandidate",
    "CandidateMap",
    "ProviderResult",
    "ScreenIdentity",
    "FingerprintBuilder",
    "DynamicRegionMasker",
]
