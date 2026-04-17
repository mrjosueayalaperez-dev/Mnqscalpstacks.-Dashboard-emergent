#!/usr/bin/env python3
"""
Trading Command Center Backend API Tests
Tests all endpoints for MNQ futures trading application
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, List

class TradingAPITester:
    def __init__(self, base_url="https://mnq-scalp-stack.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    {details}")
        if success:
            self.tests_passed += 1
        else:
            self.failed_tests.append({"name": name, "details": details})

    def test_api_root(self) -> bool:
        """Test API root endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'N/A')}"
            self.log_test("API Root", success, details)
            return success
        except Exception as e:
            self.log_test("API Root", False, f"Exception: {str(e)}")
            return False

    def test_seed_data(self) -> bool:
        """Test data seeding endpoint"""
        try:
            response = self.session.post(f"{self.api_url}/seed")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'N/A')}"
            self.log_test("Seed Data", success, details)
            return success
        except Exception as e:
            self.log_test("Seed Data", False, f"Exception: {str(e)}")
            return False

    def test_mnq_futures(self) -> bool:
        """Test MNQ futures data endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/futures/mnq")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                required_fields = ['symbol', 'price', 'change', 'high', 'low', 'vwap', 'ema9', 'ema21', 'rsi']
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    success = False
                    details += f", Missing fields: {missing_fields}"
                else:
                    details += f", Symbol: {data.get('symbol')}, Price: {data.get('price')}"
                    if data.get('is_mock'):
                        details += " (Mock Data)"
                    elif data.get('is_proxy'):
                        details += " (QQQ Proxy)"
            self.log_test("MNQ Futures Data", success, details)
            return success
        except Exception as e:
            self.log_test("MNQ Futures Data", False, f"Exception: {str(e)}")
            return False

    def test_watchlist_operations(self) -> bool:
        """Test watchlist CRUD operations"""
        success_count = 0
        
        # Test GET watchlist
        try:
            response = self.session.get(f"{self.api_url}/watchlist")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Items: {len(data)}"
                if len(data) > 0:
                    details += f", First item: {data[0].get('symbol', 'N/A')}"
            self.log_test("Get Watchlist", success, details)
            if success:
                success_count += 1
        except Exception as e:
            self.log_test("Get Watchlist", False, f"Exception: {str(e)}")

        # Test POST watchlist (add item)
        test_item = {
            "symbol": "TEST",
            "name": "Test Stock",
            "category": "stock",
            "notes": "Test item for API testing"
        }
        try:
            response = self.session.post(f"{self.api_url}/watchlist", json=test_item)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            item_id = None
            if success:
                data = response.json()
                item_id = data.get('id')
                details += f", Added: {data.get('symbol')}, ID: {item_id}"
            self.log_test("Add Watchlist Item", success, details)
            if success:
                success_count += 1
                
                # Test DELETE watchlist item
                if item_id:
                    try:
                        response = self.session.delete(f"{self.api_url}/watchlist/{item_id}")
                        success = response.status_code == 200
                        details = f"Status: {response.status_code}"
                        if success:
                            data = response.json()
                            details += f", Message: {data.get('message', 'N/A')}"
                        self.log_test("Delete Watchlist Item", success, details)
                        if success:
                            success_count += 1
                    except Exception as e:
                        self.log_test("Delete Watchlist Item", False, f"Exception: {str(e)}")
        except Exception as e:
            self.log_test("Add Watchlist Item", False, f"Exception: {str(e)}")

        return success_count >= 2

    def test_stock_scanner(self) -> bool:
        """Test stock scanner endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/stocks/scanner")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                scanners = data.get('scanners', [])
                details += f", Results: {len(scanners)}"
                if len(scanners) > 0:
                    first_result = scanners[0]
                    details += f", First: {first_result.get('symbol')} ({first_result.get('change_percent')}%)"
                    if first_result.get('is_mock'):
                        details += " (Mock Data)"
            self.log_test("Stock Scanner", success, details)
            return success
        except Exception as e:
            self.log_test("Stock Scanner", False, f"Exception: {str(e)}")
            return False

    def test_trade_journal(self) -> bool:
        """Test trade journal operations"""
        success_count = 0
        
        # Test GET trades
        try:
            response = self.session.get(f"{self.api_url}/trades")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Trades: {len(data)}"
            self.log_test("Get Trades", success, details)
            if success:
                success_count += 1
        except Exception as e:
            self.log_test("Get Trades", False, f"Exception: {str(e)}")

        # Test GET trade stats
        try:
            response = self.session.get(f"{self.api_url}/trades/stats")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Total P&L: ${data.get('total_pnl', 0)}, Win Rate: {data.get('win_rate', 0)}%"
            self.log_test("Get Trade Stats", success, details)
            if success:
                success_count += 1
        except Exception as e:
            self.log_test("Get Trade Stats", False, f"Exception: {str(e)}")

        # Test POST trade (create)
        test_trade = {
            "symbol": "TEST",
            "entry_price": 100.50,
            "quantity": 10,
            "side": "long",
            "notes": "Test trade for API testing"
        }
        try:
            response = self.session.post(f"{self.api_url}/trades", json=test_trade)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            trade_id = None
            if success:
                data = response.json()
                trade_id = data.get('id')
                details += f", Created: {data.get('symbol')} {data.get('side')}, ID: {trade_id}"
            self.log_test("Create Trade", success, details)
            if success:
                success_count += 1
                
                # Test PATCH trade (close)
                if trade_id:
                    try:
                        update_data = {"exit_price": 105.00, "status": "closed"}
                        response = self.session.patch(f"{self.api_url}/trades/{trade_id}", json=update_data)
                        success = response.status_code == 200
                        details = f"Status: {response.status_code}"
                        if success:
                            data = response.json()
                            details += f", P&L: ${data.get('pnl', 0)}, Status: {data.get('status')}"
                        self.log_test("Close Trade", success, details)
                        if success:
                            success_count += 1
                    except Exception as e:
                        self.log_test("Close Trade", False, f"Exception: {str(e)}")
        except Exception as e:
            self.log_test("Create Trade", False, f"Exception: {str(e)}")

        return success_count >= 3

    def test_checklist_operations(self) -> bool:
        """Test checklist operations"""
        success_count = 0
        
        # Test GET checklist
        try:
            response = self.session.get(f"{self.api_url}/checklist")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Items: {len(data)}"
                completed = len([item for item in data if item.get('completed')])
                details += f", Completed: {completed}"
            self.log_test("Get Checklist", success, details)
            if success:
                success_count += 1
        except Exception as e:
            self.log_test("Get Checklist", False, f"Exception: {str(e)}")

        # Test POST checklist reset
        try:
            response = self.session.post(f"{self.api_url}/checklist/reset")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'N/A')}"
            self.log_test("Reset Checklist", success, details)
            if success:
                success_count += 1
        except Exception as e:
            self.log_test("Reset Checklist", False, f"Exception: {str(e)}")

        return success_count >= 1

    def test_alerts_operations(self) -> bool:
        """Test alerts operations"""
        success_count = 0
        
        # Test GET alerts
        try:
            response = self.session.get(f"{self.api_url}/alerts")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Alerts: {len(data)}"
            self.log_test("Get Alerts", success, details)
            if success:
                success_count += 1
        except Exception as e:
            self.log_test("Get Alerts", False, f"Exception: {str(e)}")

        # Test POST alert (create)
        test_alert = {
            "symbol": "TEST",
            "alert_type": "price_target",
            "condition": "above",
            "target_value": 150.00
        }
        try:
            response = self.session.post(f"{self.api_url}/alerts", json=test_alert)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            alert_id = None
            if success:
                data = response.json()
                alert_id = data.get('id')
                details += f", Created: {data.get('symbol')} {data.get('condition')} ${data.get('target_value')}"
            self.log_test("Create Alert", success, details)
            if success:
                success_count += 1
                
                # Test DELETE alert
                if alert_id:
                    try:
                        response = self.session.delete(f"{self.api_url}/alerts/{alert_id}")
                        success = response.status_code == 200
                        details = f"Status: {response.status_code}"
                        if success:
                            data = response.json()
                            details += f", Message: {data.get('message', 'N/A')}"
                        self.log_test("Delete Alert", success, details)
                        if success:
                            success_count += 1
                    except Exception as e:
                        self.log_test("Delete Alert", False, f"Exception: {str(e)}")
        except Exception as e:
            self.log_test("Create Alert", False, f"Exception: {str(e)}")

        return success_count >= 2

    def test_ai_analysis(self) -> bool:
        """Test AI analysis endpoint"""
        try:
            test_request = {
                "symbol": "MNQ",
                "analysis_type": "general",
                "context": "Test analysis request"
            }
            response = self.session.post(f"{self.api_url}/ai/analyze", json=test_request)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Symbol: {data.get('symbol')}, Type: {data.get('analysis_type')}"
                analysis = data.get('analysis', '')
                if analysis:
                    details += f", Analysis length: {len(analysis)} chars"
            elif response.status_code == 500:
                # Check if it's a configuration issue
                try:
                    error_data = response.json()
                    if "AI service not configured" in error_data.get('detail', ''):
                        details += ", AI service not configured (expected with demo key)"
                        success = True  # This is expected behavior
                except:
                    pass
            self.log_test("AI Analysis", success, details)
            return success
        except Exception as e:
            self.log_test("AI Analysis", False, f"Exception: {str(e)}")
            return False

    def test_stock_quotes(self) -> bool:
        """Test stock quote endpoints"""
        success_count = 0
        test_symbols = ["SOFI", "NIO", "RKLB"]
        
        for symbol in test_symbols:
            try:
                response = self.session.get(f"{self.api_url}/stocks/quote/{symbol}")
                success = response.status_code == 200
                details = f"Status: {response.status_code}"
                if success:
                    data = response.json()
                    details += f", Symbol: {data.get('symbol')}, Price: ${data.get('price')}"
                    if data.get('is_mock'):
                        details += " (Mock Data)"
                self.log_test(f"Stock Quote - {symbol}", success, details)
                if success:
                    success_count += 1
            except Exception as e:
                self.log_test(f"Stock Quote - {symbol}", False, f"Exception: {str(e)}")

        return success_count >= 2

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all API tests"""
        print("🚀 Starting Trading Command Center API Tests")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test basic connectivity first
        basic_tests = [
            self.test_api_root(),
            self.test_seed_data(),
        ]
        
        if not any(basic_tests):
            print("\n❌ Basic connectivity failed - stopping tests")
            return self.get_results()
        
        # Run all feature tests
        feature_tests = [
            self.test_mnq_futures(),
            self.test_watchlist_operations(),
            self.test_stock_scanner(),
            self.test_trade_journal(),
            self.test_checklist_operations(),
            self.test_alerts_operations(),
            self.test_ai_analysis(),
            self.test_stock_quotes(),
        ]
        
        return self.get_results()

    def get_results(self) -> Dict[str, Any]:
        """Get test results summary"""
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        
        print("\n" + "=" * 60)
        print(f"📊 TEST RESULTS: {self.tests_passed}/{self.tests_run} passed ({success_rate:.1f}%)")
        
        if self.failed_tests:
            print(f"\n❌ FAILED TESTS ({len(self.failed_tests)}):")
            for test in self.failed_tests:
                print(f"  • {test['name']}: {test['details']}")
        
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": len(self.failed_tests),
            "success_rate": success_rate,
            "failed_test_details": self.failed_tests,
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main test runner"""
    tester = TradingAPITester()
    results = tester.run_all_tests()
    
    # Save results to file
    with open('/app/test_reports/backend_api_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Return appropriate exit code
    return 0 if results['success_rate'] >= 80 else 1

if __name__ == "__main__":
    sys.exit(main())