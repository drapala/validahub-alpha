"""Test value object contracts without implementation coupling."""

import dataclasses

import pytest

from src.domain.value_objects import IdempotencyKey, TenantId


def as_str(vo):
    """Helper to avoid depending on .value attribute."""
    return str(vo)


class TestVOContracts:
    """Test value object behavioral contracts."""
    
    def test_tenant_id_equality_by_value(self):
        """TenantId equality should be based on normalized value."""
        
        a = TenantId("t_acme123")
        b = TenantId("T_ACME123")  # Different case
        c = TenantId("t_zen456")
        
        assert a == b
        assert a != c
    
    def test_tenant_id_is_immutable(self):
        """TenantId should be immutable."""
        
        t = TenantId("t_acme123")
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.value = "t_mutated"
    
    def test_idempotency_key_equality_by_value(self):
        """IdempotencyKey equality should be based on value."""
        
        a = IdempotencyKey("test-key-123-abc-def")
        b = IdempotencyKey("test-key-123-abc-def")
        c = IdempotencyKey("other-key-456-ghi-jkl")
        
        assert a == b
        assert a != c
    
    def test_idempotency_key_is_immutable(self):
        """IdempotencyKey should be immutable."""
        
        key = IdempotencyKey("test-key-123-immut-test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            key.value = "mutated-key"
    
    def test_value_objects_are_hashable(self):
        """Value objects should be hashable for use in sets/dicts."""
        
        tenant_set = {TenantId("t_acme123"), TenantId("t_zen456")}
        assert len(tenant_set) == 2
        
        key_dict = {
            IdempotencyKey("key-1-hashable-test-abc"): "value1",
            IdempotencyKey("key-2-hashable-test-def"): "value2",
        }
        assert len(key_dict) == 2
    
    def test_value_objects_string_representation(self):
        """Value objects should have meaningful string representation."""
        
        tenant = TenantId("t_acme123")
        assert as_str(tenant) == "t_acme123"
        
        key = IdempotencyKey("test-key-123-string-repr")
        assert as_str(key) == "test-key-123-string-repr"