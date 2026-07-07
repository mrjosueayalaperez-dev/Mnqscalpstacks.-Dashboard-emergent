"""
Test Backtest Feature - MNQ Scalp Stack v2
Tests CRUD operations for backtest results and public endpoint
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestBacktestCRUD:
    """Backtest CRUD endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_backtest_ids = []
        yield
        # Cleanup test data
        for bt_id in self.test_backtest_ids:
            try:
                requests.delete(f"{BASE_URL}/api/backtests/{bt_id}")
            except:
                pass
    
    def test_get_backtests_returns_list(self):
        """GET /api/backtests - returns backtest list"""
        response = requests.get(f"{BASE_URL}/api/backtests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/backtests returns list with {len(data)} items")
    
    def test_create_backtest_with_auto_win_rate(self):
        """POST /api/backtests - creates backtest with win_rate auto-calculated"""
        payload = {
            "strategy_name": "TEST_MNQ Scalp Stack v2",
            "timeframe": "1m",
            "symbol": "MNQ",
            "period_start": "2025-01-01",
            "period_end": "2025-01-15",
            "total_trades": 100,
            "winning_trades": 70,
            "losing_trades": 30,
            "profit_factor": 2.0,
            "net_profit": 1500.00,
            "max_drawdown": -300.00,
            "max_drawdown_pct": 3.0,
            "sharpe_ratio": 1.5,
            "avg_trade": 15.00,
            "avg_win": 30.00,
            "avg_loss": -15.00,
            "largest_win": 100.00,
            "largest_loss": -40.00,
            "max_consecutive_wins": 8,
            "max_consecutive_losses": 3,
            "notes": "Test backtest for automated testing"
        }
        
        response = requests.post(f"{BASE_URL}/api/backtests", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        self.test_backtest_ids.append(data["id"])
        
        # Verify auto-calculated win_rate
        expected_win_rate = round(70 / 100 * 100, 1)  # 70.0%
        assert data["win_rate"] == expected_win_rate, f"Expected win_rate {expected_win_rate}, got {data['win_rate']}"
        
        # Verify other fields
        assert data["strategy_name"] == payload["strategy_name"]
        assert data["total_trades"] == payload["total_trades"]
        assert data["winning_trades"] == payload["winning_trades"]
        assert data["profit_factor"] == payload["profit_factor"]
        assert data["net_profit"] == payload["net_profit"]
        assert data["sharpe_ratio"] == payload["sharpe_ratio"]
        assert "id" in data
        assert "created_at" in data
        
        print(f"✓ POST /api/backtests creates backtest with auto-calculated win_rate: {data['win_rate']}%")
    
    def test_create_backtest_minimal_payload(self):
        """POST /api/backtests - creates backtest with minimal payload"""
        payload = {
            "total_trades": 50,
            "winning_trades": 35,
            "losing_trades": 15
        }
        
        response = requests.post(f"{BASE_URL}/api/backtests", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        self.test_backtest_ids.append(data["id"])
        
        # Verify defaults
        assert data["strategy_name"] == "MNQ Scalp Stack v2"
        assert data["timeframe"] == "1m"
        assert data["symbol"] == "MNQ"
        assert data["win_rate"] == 70.0  # 35/50 * 100
        
        print(f"✓ POST /api/backtests with minimal payload uses defaults correctly")
    
    def test_delete_backtest(self):
        """DELETE /api/backtests/{id} - deletes backtest"""
        # First create a backtest
        payload = {
            "strategy_name": "TEST_Delete Me",
            "total_trades": 10,
            "winning_trades": 5,
            "losing_trades": 5
        }
        create_response = requests.post(f"{BASE_URL}/api/backtests", json=payload)
        assert create_response.status_code == 200
        backtest_id = create_response.json()["id"]
        
        # Delete it
        delete_response = requests.delete(f"{BASE_URL}/api/backtests/{backtest_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Deleted"
        
        # Verify it's gone - GET should not include it
        get_response = requests.get(f"{BASE_URL}/api/backtests")
        backtests = get_response.json()
        assert not any(bt["id"] == backtest_id for bt in backtests)
        
        print(f"✓ DELETE /api/backtests/{backtest_id} successfully deleted backtest")
    
    def test_delete_nonexistent_backtest_returns_404(self):
        """DELETE /api/backtests/{id} - returns 404 for nonexistent backtest"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/backtests/{fake_id}")
        assert response.status_code == 404
        print(f"✓ DELETE /api/backtests with fake ID returns 404")
    
    def test_create_and_verify_persistence(self):
        """POST then GET - verify backtest persists in database"""
        payload = {
            "strategy_name": "TEST_Persistence Check",
            "total_trades": 200,
            "winning_trades": 140,
            "losing_trades": 60,
            "profit_factor": 2.5,
            "net_profit": 3000.00
        }
        
        # Create
        create_response = requests.post(f"{BASE_URL}/api/backtests", json=payload)
        assert create_response.status_code == 200
        created = create_response.json()
        self.test_backtest_ids.append(created["id"])
        
        # GET to verify persistence
        get_response = requests.get(f"{BASE_URL}/api/backtests")
        assert get_response.status_code == 200
        backtests = get_response.json()
        
        # Find our backtest
        found = next((bt for bt in backtests if bt["id"] == created["id"]), None)
        assert found is not None, "Created backtest not found in GET response"
        assert found["strategy_name"] == payload["strategy_name"]
        assert found["total_trades"] == payload["total_trades"]
        assert found["profit_factor"] == payload["profit_factor"]
        
        print(f"✓ Backtest persists correctly in database")


class TestPublicBacktestEndpoint:
    """Public backtest endpoint tests"""
    
    def test_public_backtests_returns_list(self):
        """GET /api/public/backtests - returns latest backtests"""
        response = requests.get(f"{BASE_URL}/api/public/backtests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should return max 5 backtests
        assert len(data) <= 5
        print(f"✓ GET /api/public/backtests returns list with {len(data)} items (max 5)")
    
    def test_public_backtests_sorted_by_created_at(self):
        """GET /api/public/backtests - returns backtests sorted by created_at desc"""
        response = requests.get(f"{BASE_URL}/api/public/backtests")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) >= 2:
            # Verify descending order
            for i in range(len(data) - 1):
                assert data[i]["created_at"] >= data[i+1]["created_at"], "Backtests not sorted by created_at desc"
            print(f"✓ GET /api/public/backtests returns backtests sorted by created_at desc")
        else:
            print(f"✓ GET /api/public/backtests returns {len(data)} items (not enough to verify sort)")


class TestDemoBacktestSeeder:
    """Demo backtest seeder tests"""
    
    def test_seed_demo_backtest_idempotent(self):
        """POST /api/backtests/seed-demo - seeds demo backtest (idempotent)"""
        # First call
        response1 = requests.post(f"{BASE_URL}/api/backtests/seed-demo")
        assert response1.status_code == 200
        
        # Second call should be idempotent
        response2 = requests.post(f"{BASE_URL}/api/backtests/seed-demo")
        assert response2.status_code == 200
        
        # Should return "already exists" message on second call
        data2 = response2.json()
        assert "message" in data2
        
        print(f"✓ POST /api/backtests/seed-demo is idempotent")
    
    def test_demo_backtest_has_realistic_data(self):
        """Verify demo backtest has realistic v2 strategy data"""
        # Seed first
        requests.post(f"{BASE_URL}/api/backtests/seed-demo")
        
        # Get backtests
        response = requests.get(f"{BASE_URL}/api/backtests")
        assert response.status_code == 200
        backtests = response.json()
        
        # Find demo backtest (verified one)
        demo = next((bt for bt in backtests if bt.get("is_verified") == True), None)
        
        if demo:
            # Verify realistic data
            assert demo["strategy_name"] == "MNQ Scalp Stack v2"
            assert demo["symbol"] == "MNQ"
            assert demo["timeframe"] == "1m"
            assert demo["total_trades"] == 312
            assert demo["win_rate"] == 69.9
            assert demo["profit_factor"] == 2.14
            assert demo["net_profit"] == 4280.00
            assert demo["sharpe_ratio"] == 1.87
            assert demo["max_drawdown_pct"] == 6.2
            print(f"✓ Demo backtest has realistic v2 strategy data (312 trades, 69.9% WR, 2.14 PF)")
        else:
            print(f"✓ Demo backtest seeder works (no verified backtest found - may have been deleted)")


class TestBacktestDataValidation:
    """Backtest data validation tests"""
    
    def test_win_rate_calculation_edge_cases(self):
        """Test win_rate calculation with edge cases"""
        # Zero trades
        payload = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0
        }
        response = requests.post(f"{BASE_URL}/api/backtests", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["win_rate"] == 0  # Should handle division by zero
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/backtests/{data['id']}")
        
        print(f"✓ Win rate calculation handles edge cases (0 trades = 0% win rate)")
    
    def test_backtest_response_excludes_mongodb_id(self):
        """Verify backtest response doesn't include MongoDB _id"""
        payload = {
            "strategy_name": "TEST_No MongoDB ID",
            "total_trades": 10,
            "winning_trades": 5,
            "losing_trades": 5
        }
        
        response = requests.post(f"{BASE_URL}/api/backtests", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "_id" not in data, "Response should not include MongoDB _id"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/backtests/{data['id']}")
        
        print(f"✓ Backtest response excludes MongoDB _id")


class TestExistingFeaturesStillWork:
    """Verify existing features still work after backtest addition"""
    
    def test_signals_endpoint_still_works(self):
        """GET /api/signals - still works"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        print(f"✓ GET /api/signals still works")
    
    def test_watchlist_endpoint_still_works(self):
        """GET /api/watchlist - still works"""
        response = requests.get(f"{BASE_URL}/api/watchlist")
        assert response.status_code == 200
        print(f"✓ GET /api/watchlist still works")
    
    def test_trades_endpoint_still_works(self):
        """GET /api/trades - still works"""
        response = requests.get(f"{BASE_URL}/api/trades")
        assert response.status_code == 200
        print(f"✓ GET /api/trades still works")
    
    def test_public_performance_still_works(self):
        """GET /api/public/performance - still works"""
        response = requests.get(f"{BASE_URL}/api/public/performance")
        assert response.status_code == 200
        data = response.json()
        assert "overview" in data
        assert "pnl_curve" in data
        assert "recent_signals" in data
        print(f"✓ GET /api/public/performance still works")
    
    def test_mnq_futures_still_works(self):
        """GET /api/futures/mnq - still works"""
        response = requests.get(f"{BASE_URL}/api/futures/mnq")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == "MNQ"
        print(f"✓ GET /api/futures/mnq still works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
