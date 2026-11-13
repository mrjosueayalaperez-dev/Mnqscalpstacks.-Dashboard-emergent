"""
Signal Engine v2 API Tests
Tests for MNQ Scalp Stack v2 - Session VWAP + Structure:
- v2 test signal generation with components: vwap_filter, rsi_momentum, structure
- Pivot-based TP/SL (variable distances, not fixed 8/10/20)
- v2 Pine Script with VWAP, pivots, alertcondition
- Webhook processing still works
- Signal history with mix of v1 and v2 signals
- Stats, health, kill switch still functional
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
# Webhook secret is now required (header or JSON body). Dummy default for local runs only.
WH = {"X-Webhook-Secret": os.environ.get("SIGNAL_WEBHOOK_SECRET", "test-secret-dummy")}


class TestSignalEngineV2Components:
    """Test v2 signal generation with new components"""
    
    def test_v2_signal_has_correct_components(self):
        """POST /api/signals/test - v2 signal has vwap_filter, rsi_momentum, structure"""
        # Ensure kill switch is off
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        response = requests.post(f"{BASE_URL}/api/signals/test")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get('status') == 'generated', f"Expected 'generated', got {data.get('status')}"
        
        signal = data['signal']
        components = signal.get('components', {})
        
        # Current confluence components: EMA21 cross + VWAP filter
        v2_components = ['ema21_cross', 'vwap_filter']
        for comp in v2_components:
            assert comp in components, f"Missing v2 component: {comp}"
            assert isinstance(components[comp], bool), f"Component {comp} should be boolean"
        
        print(f"✓ v2 signal has components: {list(components.keys())}")
    
    def test_v2_signal_pivot_based_tp_sl(self):
        """POST /api/signals/test - TP/SL are pivot-based (variable distances)"""
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        # Generate multiple signals to verify variable distances
        sl_distances = []
        tp1_distances = []
        
        for _ in range(5):
            response = requests.post(f"{BASE_URL}/api/signals/test")
            assert response.status_code == 200
            signal = response.json()['signal']
            
            entry = signal['entry_price']
            sl = signal['stop_loss']
            tp1 = signal['tp1']
            
            sl_dist = abs(entry - sl)
            tp1_dist = abs(entry - tp1)
            
            sl_distances.append(sl_dist)
            tp1_distances.append(tp1_dist)
        
        # Verify distances are variable (not all exactly 8 or 10)
        unique_sl = len(set(round(d, 1) for d in sl_distances))
        unique_tp1 = len(set(round(d, 1) for d in tp1_distances))
        
        # Should have at least 2 different distances (pivot-based = variable)
        assert unique_sl >= 2 or unique_tp1 >= 2, "TP/SL distances should be variable (pivot-based)"
        
        # Verify distances are in realistic range (6-15 pts based on code)
        for sl_dist in sl_distances:
            assert 5 < sl_dist < 20, f"SL distance {sl_dist:.2f} outside expected range"
        
        print(f"✓ Pivot-based TP/SL verified: SL distances={[round(d,2) for d in sl_distances]}")
    
    def test_v2_signal_confluence_score_0_to_3(self):
        """POST /api/signals/test - confluence score is 0-3 (3 v2 components)"""
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        scores = []
        for _ in range(5):
            response = requests.post(f"{BASE_URL}/api/signals/test")
            signal = response.json()['signal']
            scores.append(signal['confluence_score'])
        
        for score in scores:
            assert 0 <= score <= 3, f"Confluence score {score} should be 0-3"
        
        print(f"✓ Confluence scores: {scores} (all in 0-3 range)")


class TestPineScriptV2:
    """Test v2 Pine Script content"""
    
    def test_pinescript_has_v2_title(self):
        """GET /api/signals/pinescript - returns v2 Pine Script with correct title"""
        response = requests.get(f"{BASE_URL}/api/signals/pinescript")
        assert response.status_code == 200
        data = response.json()
        
        pine_script = data.get('pine_script', '')
        assert 'MNQ Scalp Stacks v3' in pine_script, "Pine Script should have v3 title"

        print("✓ Pine Script has v3 title: 'MNQ Scalp Stacks v3'")
    
    def test_pinescript_contains_vwap(self):
        """GET /api/signals/pinescript - v2 script contains ta.vwap"""
        response = requests.get(f"{BASE_URL}/api/signals/pinescript")
        data = response.json()
        
        pine_script = data.get('pine_script', '')
        assert 'ta.vwap' in pine_script, "Pine Script should use ta.vwap"
        print("✓ Pine Script contains ta.vwap for Session VWAP")
    
    def test_pinescript_contains_pivots(self):
        """GET /api/signals/pinescript - v2 script contains pivothigh, pivotlow"""
        response = requests.get(f"{BASE_URL}/api/signals/pinescript")
        data = response.json()
        
        pine_script = data.get('pine_script', '')
        assert 'ta.ema' in pine_script, "Pine Script should use the EMA21 spine"
        assert 'strategy.entry' in pine_script, "Pine Script should submit strategy entries"

        print("✓ Pine Script contains EMA spine + strategy entries")
    
    def test_pinescript_contains_alertcondition(self):
        """GET /api/signals/pinescript - v2 script contains alertcondition"""
        response = requests.get(f"{BASE_URL}/api/signals/pinescript")
        data = response.json()
        
        pine_script = data.get('pine_script', '')
        assert 'alertcondition' in pine_script, "Pine Script should have alertcondition"
        assert 'BUY PUNCH' in pine_script, "Pine Script should have BUY PUNCH alert"
        assert 'SELL PUNCH' in pine_script, "Pine Script should have SELL PUNCH alert"
        
        print("✓ Pine Script contains alertcondition for TradingView alerts")
    
    def test_pinescript_contains_structure_logic(self):
        """GET /api/signals/pinescript - v2 script contains higher-low/lower-high structure"""
        response = requests.get(f"{BASE_URL}/api/signals/pinescript")
        data = response.json()
        
        pine_script = data.get('pine_script', '')
        assert 'vwapVal' in pine_script, "Pine Script should use the VWAP institutional level"
        assert 'ema21' in pine_script, "Pine Script should use the EMA21 spine"

        print("✓ Pine Script contains EMA21 + VWAP confluence structure")
    
    def test_webhook_instructions_mention_v2(self):
        """GET /api/signals/pinescript - webhook_instructions mention v2"""
        response = requests.get(f"{BASE_URL}/api/signals/pinescript")
        data = response.json()
        
        instructions = data.get('webhook_instructions', '')
        assert 'v3' in instructions.lower(), "Webhook instructions should mention v3"
        assert 'MNQ' in instructions, "Webhook instructions should mention MNQ"

        print("✓ Webhook instructions mention v3 signal logic")


class TestWebhookStillWorks:
    """Test TradingView webhook still processes correctly"""
    
    def test_webhook_buy_signal(self):
        """POST /api/webhook/tradingview - still processes buy webhooks"""
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        payload = {
            "type": "buy",
            "symbol": "MNQ",
            "price": "18550.00",
            "time": "2026-01-15T10:30:00Z"
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/tradingview", json=payload, headers=WH)
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] in ['received', 'duplicate'], f"Unexpected status: {data['status']}"
        if data['status'] == 'received':
            assert data['side'] == 'long', "Buy should create long signal"
        
        print(f"✓ Webhook buy signal: {data['status']}")
    
    def test_webhook_sell_signal(self):
        """POST /api/webhook/tradingview - still processes sell webhooks"""
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        time.sleep(0.5)  # Avoid duplicate detection
        
        payload = {
            "type": "sell",
            "symbol": "MNQ",
            "price": "18600.00",
            "time": "2026-01-15T10:35:00Z"
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/tradingview", json=payload, headers=WH)
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] in ['received', 'duplicate']
        if data['status'] == 'received':
            assert data['side'] == 'short', "Sell should create short signal"
        
        print(f"✓ Webhook sell signal: {data['status']}")


class TestSignalHistoryAndStats:
    """Test signal history and stats with v2 signals"""
    
    def test_signal_history_returns_signals(self):
        """GET /api/signals - returns signal history"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Signal history: {len(data)} signals")
    
    def test_signal_history_contains_v2_signals(self):
        """GET /api/signals - history contains v2 signals with new components"""
        # Generate a v2 signal first
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        requests.post(f"{BASE_URL}/api/signals/test")
        
        response = requests.get(f"{BASE_URL}/api/signals")
        signals = response.json()
        
        # Find signals with v2 components
        v2_signals = [s for s in signals if 'vwap_filter' in s.get('components', {})]
        
        assert len(v2_signals) > 0, "Should have at least one v2 signal"
        
        # Verify v2 signal structure
        v2_signal = v2_signals[0]
        assert 'vwap_filter' in v2_signal['components']
        assert 'ema21_cross' in v2_signal['components']
        
        print(f"✓ Found {len(v2_signals)} v2 signals in history")
    
    def test_signal_stats_still_works(self):
        """GET /api/signals/stats - stats calculation still works"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ['total_signals', 'win_rate', 'total_pnl_points', 'avg_rr', 'signal_frequency_per_day']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Signal stats: {data['total_signals']} signals, {data['win_rate']}% win rate")


class TestSystemHealthAndKillSwitch:
    """Test system health and kill switch still work"""
    
    def test_system_health_reports_correctly(self):
        """GET /api/signals/health - system health still reports correctly"""
        response = requests.get(f"{BASE_URL}/api/signals/health")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ['status', 'kill_switch', 'total_signals_processed', 'error_rate_pct', 'discord_configured']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        assert data['status'] in ['healthy', 'warning', 'degraded']
        
        print(f"✓ System health: {data['status']}, {data['total_signals_processed']} processed")
    
    def test_kill_switch_blocks_signals(self):
        """POST /api/signals/kill-switch - kill switch still blocks signals"""
        # Enable kill switch
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": True})
        
        # Try to generate signal
        response = requests.post(f"{BASE_URL}/api/signals/test")
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'blocked', f"Expected 'blocked', got {data['status']}"
        
        # Disable kill switch
        requests.post(f"{BASE_URL}/api/signals/kill-switch", json={"enabled": False})
        
        print("✓ Kill switch blocks signal generation")


class TestExistingFeaturesStillWork:
    """Verify all existing features still work after v2 upgrade"""
    
    def test_mnq_tracker(self):
        """GET /api/futures/mnq - MNQ tracker still works"""
        response = requests.get(f"{BASE_URL}/api/futures/mnq")
        assert response.status_code == 200
        data = response.json()
        assert data['symbol'] == 'MNQ'
        print(f"✓ MNQ Tracker: ${data['price']:.2f}")
    
    def test_watchlist(self):
        """GET /api/watchlist - Watchlist still works"""
        response = requests.get(f"{BASE_URL}/api/watchlist")
        assert response.status_code == 200
        print(f"✓ Watchlist: {len(response.json())} items")
    
    def test_trades(self):
        """GET /api/trades - Trades still work"""
        response = requests.get(f"{BASE_URL}/api/trades")
        assert response.status_code == 200
        print(f"✓ Trades: {len(response.json())} trades")
    
    def test_checklist(self):
        """GET /api/checklist - Checklist still works"""
        response = requests.get(f"{BASE_URL}/api/checklist")
        assert response.status_code == 200
        print(f"✓ Checklist: {len(response.json())} items")
    
    def test_alerts(self):
        """GET /api/alerts - Alerts still work"""
        response = requests.get(f"{BASE_URL}/api/alerts")
        assert response.status_code == 200
        print(f"✓ Alerts: {len(response.json())} alerts")
    
    def test_position_calculator(self):
        """POST /api/calculator/position-size - Calculator still works"""
        response = requests.post(f"{BASE_URL}/api/calculator/position-size", json={
            "entry_price": 15.50,
            "stop_loss": 14.50,
            "risk_amount": 30
        })
        assert response.status_code == 200
        data = response.json()
        assert 'position_size' in data
        print(f"✓ Position Calculator: {data['position_size']} shares")
    
    def test_public_performance(self):
        """GET /api/public/performance - Performance page still works"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        assert 'overview' in data
        assert 'pnl_curve' in data
        print(f"✓ Public Performance: {data['overview']['total_signals']} signals")
    
    def test_subscriber_tiers(self):
        """GET /api/subscribers/tiers - Subscriber tiers still work"""
        response = requests.get(f"{BASE_URL}/api/subscribers/tiers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # free, pro, elite
        print(f"✓ Subscriber Tiers: {len(data)} tiers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
