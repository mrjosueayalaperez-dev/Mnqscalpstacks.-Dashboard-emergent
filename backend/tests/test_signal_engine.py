"""
Signal Engine API Tests
Tests for the new MNQ Stack Signal Engine features:
- Test signal generation
- Signal history retrieval
- Signal stats
- System health
- Kill switch functionality
- Signal outcome updates
- Pine Script reference
- TradingView webhook
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestSignalEngineBasics:
    """Basic Signal Engine endpoint tests"""
    
    def test_get_signals_empty_or_list(self):
        """GET /api/signals - should return list of signals"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/signals returned {len(data)} signals")
    
    def test_get_signal_stats(self):
        """GET /api/signals/stats - should return signal performance metrics"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify required fields
        required_fields = ['total_signals', 'win_rate', 'total_pnl_points', 'avg_rr', 'signal_frequency_per_day']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ GET /api/signals/stats - Total: {data['total_signals']}, Win Rate: {data['win_rate']}%")
    
    def test_get_system_health(self):
        """GET /api/signals/health - should return system health metrics"""
        response = requests.get(f"{BASE_URL}/api/signals/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify required fields
        required_fields = ['status', 'kill_switch', 'total_signals_processed', 'error_rate_pct', 'discord_configured']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        assert data['status'] in ['healthy', 'warning', 'degraded'], f"Invalid status: {data['status']}"
        print(f"✓ GET /api/signals/health - Status: {data['status']}, Discord: {data['discord_configured']}")
    
    def test_get_kill_switch_state(self):
        """GET /api/signals/kill-switch - should return kill switch state"""
        response = requests.get(f"{BASE_URL}/api/signals/kill-switch")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert 'kill_switch' in data, "Missing kill_switch field"
        assert isinstance(data['kill_switch'], bool), "kill_switch should be boolean"
        print(f"✓ GET /api/signals/kill-switch - State: {data['kill_switch']}")
    
    def test_get_pinescript(self):
        """GET /api/signals/pinescript - should return Pine Script and webhook instructions"""
        response = requests.get(f"{BASE_URL}/api/signals/pinescript")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert 'pine_script' in data, "Missing pine_script field"
        assert 'webhook_instructions' in data, "Missing webhook_instructions field"
        assert 'webhook_url' in data, "Missing webhook_url field"
        
        # Verify Pine Script contains key elements
        assert '//@version=5' in data['pine_script'], "Pine Script should have version header"
        assert 'ta.ema' in data['pine_script'], "Pine Script should define the EMA spine"
        assert 'alertcondition' in data['pine_script'], "Pine Script should have alert conditions"
        
        print(f"✓ GET /api/signals/pinescript - Pine Script length: {len(data['pine_script'])} chars")


class TestSignalGeneration:
    """Test signal generation and management"""
    
    def test_generate_test_signal(self):
        """POST /api/signals/test - should generate a test signal"""
        response = requests.post(f"{BASE_URL}/api/signals/test")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get('status') in ['generated', 'blocked'], f"Unexpected status: {data.get('status')}"
        
        if data['status'] == 'generated':
            signal = data['signal']
            # Verify signal structure
            required_fields = ['id', 'symbol', 'side', 'entry_price', 'stop_loss', 'tp1', 'tp2', 
                             'confluence_score', 'components', 'trend_direction', 'source']
            for field in required_fields:
                assert field in signal, f"Missing signal field: {field}"
            
            assert signal['symbol'] == 'MNQ', "Symbol should be MNQ"
            assert signal['side'] in ['long', 'short'], f"Invalid side: {signal['side']}"
            assert signal['source'] == 'test', "Source should be 'test'"
            assert 0 <= signal['confluence_score'] <= 3, "Confluence score should be 0-3"
            
            print(f"✓ POST /api/signals/test - Generated {signal['side'].upper()} signal at ${signal['entry_price']:.2f}")
            return signal['id']
        else:
            print(f"✓ POST /api/signals/test - Blocked (kill switch active)")
            return None
    
    def test_signal_persists_in_history(self):
        """Verify generated signal appears in history"""
        # Generate a signal first
        gen_response = requests.post(f"{BASE_URL}/api/signals/test")
        if gen_response.json().get('status') != 'generated':
            pytest.skip("Kill switch active, cannot test persistence")
        
        signal_id = gen_response.json()['signal']['id']
        
        # Fetch signals and verify it exists
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        signals = response.json()
        
        signal_ids = [s['id'] for s in signals]
        assert signal_id in signal_ids, f"Generated signal {signal_id} not found in history"
        print(f"✓ Signal {signal_id[:8]}... persisted in history")


class TestKillSwitch:
    """Test kill switch functionality"""
    
    def test_enable_kill_switch(self):
        """POST /api/signals/kill-switch - enable kill switch"""
        response = requests.post(f"{BASE_URL}/api/signals/kill-switch", json={
            "enabled": True,
            "reason": "Test kill switch"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data['kill_switch'] == True, "Kill switch should be enabled"
        print(f"✓ POST /api/signals/kill-switch - Enabled")
    
    def test_kill_switch_blocks_signals(self):
        """Verify kill switch blocks new signal generation"""
        # Ensure kill switch is enabled
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": True})
        
        # Try to generate a signal
        response = requests.post(f"{BASE_URL}/api/signals/test")
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'blocked', f"Expected 'blocked', got {data['status']}"
        assert 'kill switch' in data.get('reason', '').lower(), "Should mention kill switch"
        print(f"✓ Kill switch blocks signal generation: {data['reason']}")
    
    def test_disable_kill_switch(self):
        """POST /api/signals/kill-switch - disable kill switch"""
        response = requests.post(f"{BASE_URL}/api/signals/kill-switch", json={
            "enabled": False,
            "reason": "Re-enabling for tests"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data['kill_switch'] == False, "Kill switch should be disabled"
        print(f"✓ POST /api/signals/kill-switch - Disabled")
    
    def test_signals_work_after_disable(self):
        """Verify signals can be generated after disabling kill switch"""
        # Ensure kill switch is disabled
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        # Generate a signal
        response = requests.post(f"{BASE_URL}/api/signals/test")
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'generated', f"Expected 'generated', got {data['status']}"
        print(f"✓ Signal generation works after kill switch disabled")


class TestSignalOutcomeUpdate:
    """Test signal outcome updates"""
    
    def test_update_signal_to_hit_tp1(self):
        """PATCH /api/signals/{id} - update signal to hit_tp1"""
        # First generate a signal
        gen_response = requests.post(f"{BASE_URL}/api/signals/test")
        if gen_response.json().get('status') != 'generated':
            # Disable kill switch and try again
            requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
            gen_response = requests.post(f"{BASE_URL}/api/signals/test")
        
        signal_id = gen_response.json()['signal']['id']
        
        # Update to hit_tp1
        response = requests.patch(f"{BASE_URL}/api/signals/{signal_id}?status=hit_tp1&pnl_points=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify update
        signals = requests.get(f"{BASE_URL}/api/signals").json()
        updated_signal = next((s for s in signals if s['id'] == signal_id), None)
        
        assert updated_signal is not None, "Signal not found after update"
        assert updated_signal['status'] == 'hit_tp1', f"Status should be hit_tp1, got {updated_signal['status']}"
        assert updated_signal['outcome'] == 'win', f"Outcome should be win, got {updated_signal['outcome']}"
        assert updated_signal['pnl_points'] == 10, f"PnL points should be 10, got {updated_signal['pnl_points']}"
        
        print(f"✓ PATCH /api/signals/{signal_id[:8]}... - Updated to hit_tp1 (win, +10 pts)")
    
    def test_update_signal_to_stopped(self):
        """PATCH /api/signals/{id} - update signal to stopped (loss)"""
        # Generate a signal
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        gen_response = requests.post(f"{BASE_URL}/api/signals/test")
        signal_id = gen_response.json()['signal']['id']
        
        # Update to stopped
        response = requests.patch(f"{BASE_URL}/api/signals/{signal_id}?status=stopped&pnl_points=-8")
        assert response.status_code == 200
        
        # Verify update
        signals = requests.get(f"{BASE_URL}/api/signals").json()
        updated_signal = next((s for s in signals if s['id'] == signal_id), None)
        
        assert updated_signal['status'] == 'stopped'
        assert updated_signal['outcome'] == 'loss'
        assert updated_signal['pnl_points'] == -8
        
        print(f"✓ PATCH /api/signals/{signal_id[:8]}... - Updated to stopped (loss, -8 pts)")
    
    def test_update_nonexistent_signal(self):
        """PATCH /api/signals/{id} - should return 404 for nonexistent signal"""
        response = requests.patch(f"{BASE_URL}/api/signals/nonexistent-id-12345?status=hit_tp1")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ PATCH nonexistent signal returns 404")


class TestTradingViewWebhook:
    """Test TradingView webhook receiver"""
    
    def test_webhook_buy_signal(self):
        """POST /api/webhook/tradingview - receive buy signal"""
        # Ensure kill switch is off
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        payload = {
            "type": "buy",
            "symbol": "MNQ",
            "price": "18550.00",
            "time": "2026-01-15T10:30:00Z"
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/tradingview", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Could be 'received' or 'duplicate' if we've sent similar recently
        assert data['status'] in ['received', 'duplicate'], f"Unexpected status: {data['status']}"
        
        if data['status'] == 'received':
            assert 'signal_id' in data, "Should return signal_id"
            assert data['side'] == 'long', "Buy should create long signal"
            print(f"✓ POST /api/webhook/tradingview (buy) - Signal received: {data['signal_id'][:8]}...")
        else:
            print(f"✓ POST /api/webhook/tradingview (buy) - Duplicate detected")
    
    def test_webhook_sell_signal(self):
        """POST /api/webhook/tradingview - receive sell signal"""
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        # Wait a bit to avoid duplicate detection
        time.sleep(0.5)
        
        payload = {
            "type": "sell",
            "symbol": "MNQ",
            "price": "18600.00",
            "time": "2026-01-15T10:35:00Z"
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/tradingview", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] in ['received', 'duplicate']
        
        if data['status'] == 'received':
            assert data['side'] == 'short', "Sell should create short signal"
            print(f"✓ POST /api/webhook/tradingview (sell) - Signal received")
        else:
            print(f"✓ POST /api/webhook/tradingview (sell) - Duplicate detected")
    
    def test_webhook_blocked_by_kill_switch(self):
        """POST /api/webhook/tradingview - should be blocked when kill switch active"""
        # Enable kill switch
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": True})
        
        payload = {
            "type": "buy",
            "symbol": "MNQ",
            "price": "18500.00"
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/tradingview", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'blocked', f"Expected 'blocked', got {data['status']}"
        print(f"✓ Webhook blocked by kill switch")
        
        # Disable kill switch for other tests
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})


class TestExistingFeatures:
    """Verify existing features still work after Signal Engine addition"""
    
    def test_mnq_futures_data(self):
        """GET /api/futures/mnq - MNQ tracker still works"""
        response = requests.get(f"{BASE_URL}/api/futures/mnq")
        assert response.status_code == 200
        data = response.json()
        
        assert 'symbol' in data and data['symbol'] == 'MNQ'
        assert 'price' in data
        print(f"✓ MNQ Futures: ${data['price']:.2f}")
    
    def test_watchlist_crud(self):
        """Watchlist CRUD still works"""
        # Create
        item = {"symbol": "TEST_SIG", "name": "Test Signal Stock", "category": "stock"}
        create_res = requests.post(f"{BASE_URL}/api/watchlist", json=item)
        assert create_res.status_code == 200
        item_id = create_res.json()['id']
        
        # Read
        list_res = requests.get(f"{BASE_URL}/api/watchlist")
        assert list_res.status_code == 200
        assert any(i['id'] == item_id for i in list_res.json())
        
        # Delete
        del_res = requests.delete(f"{BASE_URL}/api/watchlist/{item_id}")
        assert del_res.status_code == 200
        
        print(f"✓ Watchlist CRUD working")
    
    def test_trade_journal(self):
        """Trade journal still works"""
        # Create trade
        trade = {"symbol": "TEST_SIG", "entry_price": 15.50, "quantity": 100, "side": "long"}
        create_res = requests.post(f"{BASE_URL}/api/trades", json=trade)
        assert create_res.status_code == 200
        trade_id = create_res.json()['id']
        
        # Get stats
        stats_res = requests.get(f"{BASE_URL}/api/trades/stats")
        assert stats_res.status_code == 200
        
        print(f"✓ Trade Journal working")
    
    def test_checklist(self):
        """Checklist still works"""
        response = requests.get(f"{BASE_URL}/api/checklist")
        assert response.status_code == 200
        print(f"✓ Checklist working ({len(response.json())} items)")
    
    def test_alerts(self):
        """Alerts still work"""
        response = requests.get(f"{BASE_URL}/api/alerts")
        assert response.status_code == 200
        print(f"✓ Alerts working ({len(response.json())} alerts)")
    
    def test_position_calculator(self):
        """Position calculator still works"""
        response = requests.post(f"{BASE_URL}/api/calculator/position-size", json={
            "entry_price": 15.50,
            "stop_loss": 14.50,
            "risk_amount": 30
        })
        assert response.status_code == 200
        data = response.json()
        assert 'position_size' in data
        print(f"✓ Position Calculator: {data['position_size']} shares")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
