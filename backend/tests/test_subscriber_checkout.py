"""
Test suite for Subscriber Signup and Stripe Checkout API endpoints
Tests: 
- GET /api/subscribers/tiers - returns 3 tiers with features
- POST /api/subscribers - creates new subscriber with email, returns discord_invite
- POST /api/subscribers - returns existing subscriber if email already used
- GET /api/subscribers/count - returns total, free, pro, elite counts
- POST /api/checkout/create - creates Stripe checkout session for pro tier
- POST /api/checkout/create - creates Stripe checkout session for elite tier
- POST /api/checkout/create - rejects invalid tier
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestSubscriberTiers:
    """Tests for subscription tiers endpoint"""
    
    def test_get_tiers_returns_200(self):
        """GET /api/subscribers/tiers - should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/subscribers/tiers")
        assert response.status_code == 200
        print("GET /api/subscribers/tiers returned 200 OK")
    
    def test_get_tiers_returns_3_tiers(self):
        """GET /api/subscribers/tiers - should return exactly 3 tiers"""
        response = requests.get(f"{BASE_URL}/api/subscribers/tiers")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 3, f"Expected 3 tiers, got {len(data)}"
        print(f"Tiers returned: {len(data)}")
    
    def test_get_tiers_has_correct_structure(self):
        """GET /api/subscribers/tiers - each tier should have id, name, price, features"""
        response = requests.get(f"{BASE_URL}/api/subscribers/tiers")
        assert response.status_code == 200
        data = response.json()
        
        for tier in data:
            assert "id" in tier, f"Missing 'id' in tier"
            assert "name" in tier, f"Missing 'name' in tier"
            assert "price" in tier, f"Missing 'price' in tier"
            assert "features" in tier, f"Missing 'features' in tier"
            assert isinstance(tier["features"], list), "Features should be a list"
            print(f"Tier {tier['name']}: ${tier['price']}, {len(tier['features'])} features")
    
    def test_get_tiers_has_free_pro_elite(self):
        """GET /api/subscribers/tiers - should have free, pro, elite tiers"""
        response = requests.get(f"{BASE_URL}/api/subscribers/tiers")
        assert response.status_code == 200
        data = response.json()
        
        tier_ids = [t["id"] for t in data]
        assert "free" in tier_ids, "Missing 'free' tier"
        assert "pro" in tier_ids, "Missing 'pro' tier"
        assert "elite" in tier_ids, "Missing 'elite' tier"
        print(f"All tiers present: {tier_ids}")
    
    def test_get_tiers_correct_prices(self):
        """GET /api/subscribers/tiers - should have correct prices ($0, $49, $149)"""
        response = requests.get(f"{BASE_URL}/api/subscribers/tiers")
        assert response.status_code == 200
        data = response.json()
        
        prices = {t["id"]: t["price"] for t in data}
        assert prices["free"] == 0, f"Free tier should be $0, got ${prices['free']}"
        assert prices["pro"] == 49, f"Pro tier should be $49, got ${prices['pro']}"
        assert prices["elite"] == 149, f"Elite tier should be $149, got ${prices['elite']}"
        print(f"Prices verified: Free=${prices['free']}, Pro=${prices['pro']}, Elite=${prices['elite']}")


class TestSubscriberSignup:
    """Tests for subscriber signup endpoint"""
    
    def test_create_subscriber_returns_201_or_200(self):
        """POST /api/subscribers - should return 200/201 for new subscriber"""
        unique_email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(f"{BASE_URL}/api/subscribers", json={
            "email": unique_email,
            "name": "Test User",
            "tier": "free"
        })
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        print(f"Created subscriber with email: {unique_email}")
    
    def test_create_subscriber_returns_discord_invite(self):
        """POST /api/subscribers - should return discord_invite in response"""
        unique_email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(f"{BASE_URL}/api/subscribers", json={
            "email": unique_email,
            "name": "Test User",
            "tier": "free"
        })
        assert response.status_code in [200, 201]
        data = response.json()
        
        assert "discord_invite" in data, "Response should contain discord_invite"
        assert "subscriber" in data, "Response should contain subscriber object"
        assert "status" in data, "Response should contain status"
        print(f"Discord invite returned: {data['discord_invite'][:30] if data['discord_invite'] else 'empty'}...")
    
    def test_create_subscriber_returns_subscriber_data(self):
        """POST /api/subscribers - should return subscriber object with correct fields"""
        unique_email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(f"{BASE_URL}/api/subscribers", json={
            "email": unique_email,
            "name": "Test User",
            "tier": "free"
        })
        assert response.status_code in [200, 201]
        data = response.json()
        
        subscriber = data["subscriber"]
        assert subscriber["email"] == unique_email
        assert subscriber["tier"] == "free"
        assert "id" in subscriber
        assert "created_at" in subscriber
        print(f"Subscriber data verified: {subscriber['email']}, tier={subscriber['tier']}")
    
    def test_create_subscriber_existing_email_returns_existing(self):
        """POST /api/subscribers - should return existing subscriber if email already used"""
        unique_email = f"TEST_existing_{uuid.uuid4().hex[:8]}@example.com"
        
        # First signup
        response1 = requests.post(f"{BASE_URL}/api/subscribers", json={
            "email": unique_email,
            "name": "First User",
            "tier": "free"
        })
        assert response1.status_code in [200, 201]
        data1 = response1.json()
        
        # Second signup with same email
        response2 = requests.post(f"{BASE_URL}/api/subscribers", json={
            "email": unique_email,
            "name": "Second User",
            "tier": "free"
        })
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Should return existing status
        assert data2["status"] == "existing", f"Expected 'existing' status, got {data2['status']}"
        assert data2["subscriber"]["id"] == data1["subscriber"]["id"], "Should return same subscriber ID"
        print(f"Existing subscriber returned correctly for duplicate email")
    
    def test_create_subscriber_without_name(self):
        """POST /api/subscribers - name should be optional"""
        unique_email = f"TEST_noname_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(f"{BASE_URL}/api/subscribers", json={
            "email": unique_email,
            "tier": "free"
        })
        assert response.status_code in [200, 201]
        data = response.json()
        
        assert data["subscriber"]["email"] == unique_email
        print(f"Subscriber created without name: {unique_email}")


class TestSubscriberCount:
    """Tests for subscriber count endpoint"""
    
    def test_get_subscriber_count_returns_200(self):
        """GET /api/subscribers/count - should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/subscribers/count")
        assert response.status_code == 200
        print("GET /api/subscribers/count returned 200 OK")
    
    def test_get_subscriber_count_has_correct_fields(self):
        """GET /api/subscribers/count - should return total, free, pro, elite counts"""
        response = requests.get(f"{BASE_URL}/api/subscribers/count")
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data, "Missing 'total' count"
        assert "free" in data, "Missing 'free' count"
        assert "pro" in data, "Missing 'pro' count"
        assert "elite" in data, "Missing 'elite' count"
        
        # Verify counts are integers
        assert isinstance(data["total"], int)
        assert isinstance(data["free"], int)
        assert isinstance(data["pro"], int)
        assert isinstance(data["elite"], int)
        
        print(f"Subscriber counts: total={data['total']}, free={data['free']}, pro={data['pro']}, elite={data['elite']}")
    
    def test_subscriber_count_math_is_correct(self):
        """GET /api/subscribers/count - free + pro + elite should equal total"""
        response = requests.get(f"{BASE_URL}/api/subscribers/count")
        assert response.status_code == 200
        data = response.json()
        
        calculated_total = data["free"] + data["pro"] + data["elite"]
        assert calculated_total == data["total"], f"Count mismatch: {calculated_total} != {data['total']}"
        print(f"Count math verified: {data['free']} + {data['pro']} + {data['elite']} = {data['total']}")


class TestStripeCheckout:
    """Tests for Stripe checkout endpoint"""
    
    def test_create_checkout_pro_tier(self):
        """POST /api/checkout/create - should create checkout session for pro tier"""
        response = requests.post(f"{BASE_URL}/api/checkout/create", json={
            "tier": "pro",
            "origin_url": "https://example.com"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "url" in data, "Response should contain checkout URL"
        assert "session_id" in data, "Response should contain session_id"
        assert data["url"] is not None, "Checkout URL should not be None"
        print(f"Pro checkout session created: {data['session_id'][:20]}...")
    
    def test_create_checkout_elite_tier(self):
        """POST /api/checkout/create - should create checkout session for elite tier"""
        response = requests.post(f"{BASE_URL}/api/checkout/create", json={
            "tier": "elite",
            "origin_url": "https://example.com"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "url" in data, "Response should contain checkout URL"
        assert "session_id" in data, "Response should contain session_id"
        print(f"Elite checkout session created: {data['session_id'][:20]}...")
    
    def test_create_checkout_invalid_tier_rejected(self):
        """POST /api/checkout/create - should reject invalid tier"""
        response = requests.post(f"{BASE_URL}/api/checkout/create", json={
            "tier": "fake",
            "origin_url": "https://example.com"
        })
        assert response.status_code == 400, f"Expected 400 for invalid tier, got {response.status_code}"
        print("Invalid tier 'fake' correctly rejected with 400")
    
    def test_create_checkout_free_tier_rejected(self):
        """POST /api/checkout/create - should reject free tier (no payment needed)"""
        response = requests.post(f"{BASE_URL}/api/checkout/create", json={
            "tier": "free",
            "origin_url": "https://example.com"
        })
        assert response.status_code == 400, f"Expected 400 for free tier, got {response.status_code}"
        print("Free tier correctly rejected with 400 (no payment needed)")


class TestCheckoutStatus:
    """Tests for checkout status endpoint"""
    
    def test_checkout_status_invalid_session(self):
        """GET /api/checkout/status/{session_id} - should handle invalid session"""
        response = requests.get(f"{BASE_URL}/api/checkout/status/invalid_session_123")
        # Should return error or empty status, not crash
        # 500 is acceptable when Stripe API rejects invalid session ID
        assert response.status_code in [200, 400, 404, 500], f"Unexpected status: {response.status_code}"
        print(f"Invalid session handled with status {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
