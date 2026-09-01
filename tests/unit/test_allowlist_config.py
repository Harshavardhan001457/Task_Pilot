from astra_sentinel.config import default_config
from astra_sentinel.config.allowlist import DEFAULT_ENABLED_CAPABILITIES, DEFAULT_PERMISSION_GRANTS


def test_default_config_uses_external_allowlist():
    config = default_config()

    assert config.enabled_capabilities == DEFAULT_ENABLED_CAPABILITIES
    assert config.policy.permission_grants.grants == DEFAULT_PERMISSION_GRANTS
