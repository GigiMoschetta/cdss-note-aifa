"""aifa_rule_engine — neuro-symbolic CDSS for AIFA Note rimborsabilità.

Single source of truth for the engine version string. All call sites that
previously hardcoded "3.4.0" should import this constant instead.
"""
ENGINE_VERSION = "3.4.0"

__all__ = ["ENGINE_VERSION"]
