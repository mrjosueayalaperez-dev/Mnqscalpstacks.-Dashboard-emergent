"""
Test suite for Public Performance Dashboard API endpoints
Tests: GET /api/public/performance, POST /api/public/seed-demo
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestPublicPerformanceAPI:
    """Tests for the public performance dashboard endpoints"""
    
    def test_seed_demo_idempotent(self):
        """POST /api/public/seed-demo - should be idempotent (already seeded)"""
        response = requests.post(f"{BASE_URL}/api/public/seed-demo")
        assert response.status_code == 200
        data = response.json()
        # Should return message indicating already seeded or success
        assert "message" in data
        print(f"Seed demo response: {data['message']}")
    
    def test_get_public_performance_returns_200(self):
        """GET /api/public/performance - should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        print("GET /api/public/performance returned 200 OK")
    
    def test_public_performance_has_overview(self):
        """GET /api/public/performance - should have overview stats"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        # Check overview exists
        assert "overview" in data
        overview = data["overview"]
        
        # Check required overview fields
        required_fields = [
            "total_signals", "closed_signals", "active_signals",
            "win_rate", "total_pnl_points", "avg_win_points",
            "avg_loss_points", "avg_rr", "best_win_streak",
            "wins", "losses"
        ]
        for field in required_fields:
            assert field in overview, f"Missing field: {field}"
            print(f"  {field}: {overview[field]}")
        
        # Validate data types
        assert isinstance(overview["total_signals"], int)
        assert isinstance(overview["win_rate"], (int, float))
        assert isinstance(overview["total_pnl_points"], (int, float))
        print("Overview stats validated successfully")
    
    def test_public_performance_has_pnl_curve(self):
        """GET /api/public/performance - should have pnl_curve data"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        # Check pnl_curve exists
        assert "pnl_curve" in data
        pnl_curve = data["pnl_curve"]
        
        # Should be a list
        assert isinstance(pnl_curve, list)
        print(f"P&L curve has {len(pnl_curve)} data points")
        
        # If there's data, validate structure
        if len(pnl_curve) > 0:
            first_point = pnl_curve[0]
            assert "date" in first_point
            assert "pnl" in first_point
            assert "side" in first_point
            assert "outcome" in first_point
            print(f"First data point: date={first_point['date']}, pnl={first_point['pnl']}")
    
    def test_public_performance_has_recent_signals(self):
        """GET /api/public/performance - should have recent_signals list"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        # Check recent_signals exists
        assert "recent_signals" in data
        recent_signals = data["recent_signals"]
        
        # Should be a list
        assert isinstance(recent_signals, list)
        print(f"Recent signals has {len(recent_signals)} entries")
        
        # If there's data, validate structure
        if len(recent_signals) > 0:
            first_signal = recent_signals[0]
            required_fields = [
                "id", "symbol", "side", "entry_price",
                "tp1", "tp2", "stop_loss", "confluence_score",
                "status", "created_at"
            ]
            for field in required_fields:
                assert field in first_signal, f"Missing field in signal: {field}"
            
            print(f"First signal: {first_signal['side']} {first_signal['symbol']} @ {first_signal['entry_price']}")
    
    def test_public_performance_win_rate_calculation(self):
        """Verify win rate is calculated correctly"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        overview = data["overview"]
        wins = overview["wins"]
        losses = overview["losses"]
        closed = overview["closed_signals"]
        win_rate = overview["win_rate"]
        
        # Verify win rate calculation
        if closed > 0:
            expected_win_rate = round(wins / closed * 100, 1)
            assert abs(win_rate - expected_win_rate) < 0.2, f"Win rate mismatch: {win_rate} vs expected {expected_win_rate}"
            print(f"Win rate verified: {wins}/{closed} = {win_rate}%")
        
        # Verify wins + losses <= closed
        assert wins + losses <= closed, "Wins + losses should not exceed closed signals"
    
    def test_public_performance_pnl_curve_sorted(self):
        """Verify P&L curve is sorted by date"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        pnl_curve = data["pnl_curve"]
        if len(pnl_curve) > 1:
            dates = [p["date"] for p in pnl_curve]
            # Check dates are in ascending order
            assert dates == sorted(dates), "P&L curve should be sorted by date"
            print(f"P&L curve dates verified: {dates[0]} to {dates[-1]}")
    
    def test_recent_signals_limited_to_15(self):
        """Verify recent signals is limited to 15 entries"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        recent_signals = data["recent_signals"]
        assert len(recent_signals) <= 15, f"Recent signals should be limited to 15, got {len(recent_signals)}"
        print(f"Recent signals count: {len(recent_signals)} (max 15)")


class TestPublicPerformanceDataIntegrity:
    """Tests for data integrity in public performance"""
    
    def test_demo_data_exists(self):
        """Verify demo data was seeded"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        # Should have signals from demo seeding
        assert data["overview"]["total_signals"] > 0, "Should have demo signals"
        print(f"Total signals: {data['overview']['total_signals']}")
    
    def test_positive_expectancy(self):
        """Verify demo data shows positive expectancy (as designed)"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        
        overview = data["overview"]
        # Demo data is designed with ~69% win rate and positive expectancy
        assert overview["win_rate"] >= 50, f"Win rate should be >= 50%, got {overview['win_rate']}%"
        assert overview["total_pnl_points"] > 0, f"Total P&L should be positive, got {overview['total_pnl_points']}"
        print(f"Positive expectancy verified: {overview['win_rate']}% win rate, +{overview['total_pnl_points']} pts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
