from astra_sentinel.config import default_config
from astra_sentinel.config.allowlist import DEFAULT_ALLOWED_FILESYSTEM_ROOTS, DEFAULT_ALLOW_MODIFY, DEFAULT_ENABLED_CAPABILITIES, DEFAULT_PERMISSION_GRANTS


def test_default_config_uses_external_allowlist():
    config = default_config()

    assert config.enabled_capabilities == DEFAULT_ENABLED_CAPABILITIES
    assert config.policy.permission_grants.grants == DEFAULT_PERMISSION_GRANTS
    assert config.policy.allow_modify is DEFAULT_ALLOW_MODIFY
    assert all(str(root) in DEFAULT_ALLOWED_FILESYSTEM_ROOTS for root in config.allowed_filesystem_roots)
