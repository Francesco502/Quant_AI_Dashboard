
import pytest
import pandas as pd
import os
from unittest.mock import MagicMock, patch
from core.feature_store import FeatureStore, get_feature_store

class TestFeatureStore:
    @pytest.fixture
    def mock_feature_engineer(self):
        with patch('core.feature_store.FeatureEngineer') as MockClass:
            mock_instance = MockClass.return_value
            # Setup mock return values
            mock_instance.create_price_features.return_value = pd.DataFrame({'close': [1, 2, 3]})
            mock_instance.create_lag_features.return_value = pd.DataFrame({'close': [1, 2, 3], 'return_1d_lag1': [0, 1, 2]})
            mock_instance.add_enhanced_features.return_value = pd.DataFrame({'close': [1, 2, 3], 'return_1d_lag1': [0, 1, 2], 'enhanced': [0, 0, 0]})
            yield mock_instance

    @pytest.fixture
    def feature_store(self, mock_feature_engineer):
        # Mock load_feature_meta to return default
        with patch('core.feature_store.load_feature_meta', return_value={
            "version": "v1.0",
            "feature_list": [],
            "lookback_windows": [5, 10]
        }):
            store = FeatureStore()
            store.feature_engineer = mock_feature_engineer
            return store

    def test_singleton(self):
        s1 = get_feature_store()
        s2 = get_feature_store()
        assert s1 is s2

    def test_compute_features(self, feature_store):
        price_series = pd.Series([10, 11, 12], index=pd.date_range('2023-01-01', periods=3))
        df = feature_store.compute_features(price_series)
        
        # Verify calls
        feature_store.feature_engineer.create_price_features.assert_called()
        feature_store.feature_engineer.create_lag_features.assert_called()
        feature_store.feature_engineer.add_enhanced_features.assert_called()
        
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    @patch('core.feature_store.pd.DataFrame.to_parquet')
    @patch('core.feature_store.save_feature_meta')
    @patch('core.feature_store._ensure_dirs')
    def test_save_features(self, mock_ensure, mock_save_meta, mock_to_parquet, feature_store):
        df = pd.DataFrame({'feat1': [1, 2]}, index=pd.date_range('2023-01-01', periods=2))
        success = feature_store.save_features('000001', df)
        
        assert success is True
        mock_ensure.assert_called()
        mock_to_parquet.assert_called()
        mock_save_meta.assert_called()

    @patch('core.feature_store.pd.read_parquet')
    @patch('core.feature_store.os.path.exists', return_value=True)
    def test_load_features(self, mock_exists, mock_read, feature_store):
        mock_read.return_value = pd.DataFrame(
            {'feat1': [1, 2, 3]}, 
            index=pd.date_range('2023-01-01', periods=3)
        )
        
        df = feature_store.load_features('000001')
        assert not df.empty
        assert len(df) == 3
        
        # Test date filtering
        df_filtered = feature_store.load_features('000001', start_date='2023-01-02')
        assert len(df_filtered) == 2

    def test_update_features_for_ticker(self, feature_store):
        with patch.object(feature_store, 'save_features', return_value=True) as mock_save:
            price_series = pd.Series([10, 11, 12], index=pd.date_range('2023-01-01', periods=3))
            success = feature_store.update_features_for_ticker('000001', price_series)
            assert success is True
            mock_save.assert_called()
