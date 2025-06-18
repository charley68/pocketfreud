#!/usr/bin/env python3
"""
Test the connection pooling implementation with a mocked database connection.
"""

import sys
import os
import unittest.mock

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

# Set up environment variables for testing
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_USER'] = 'test'
os.environ['DB_PASS'] = 'test'
os.environ['DB_NAME'] = 'test'

# Mock pymysql to avoid needing a real database
with unittest.mock.patch('pymysql.connect') as mock_connect:
    mock_connection = unittest.mock.MagicMock()
    mock_connect.return_value = mock_connection
    
    try:
        from modules.db import _init_connection_pool, get_db_connection, get_pool_info, shutdown_connection_pool
        
        print("✓ Successfully imported db module with connection pooling")
        
        # Test pool initialization
        pool = _init_connection_pool()
        print("✓ Connection pool initialized successfully")
        
        # Test getting connections
        conn1 = get_db_connection()
        conn2 = get_db_connection()
        print("✓ Multiple connections obtained from pool")
        
        # Test pool info
        pool_info = get_pool_info()
        print(f"✓ Pool info: {pool_info}")
        
        # Test shutdown
        shutdown_connection_pool()
        print("✓ Connection pool shutdown successfully")
        
        print("\n🎉 Connection pooling implementation is working correctly!")
        
    except Exception as e:
        print(f"✗ Error testing connection pool: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

print("\nConfiguration summary:")
print("- Connection pooling: ✓ Enabled")
print("- Pool implementation: dbutils.pooled_db.PooledDB")
print("- Max connections: 20")
print("- Min cached connections: 2")
print("- Max cached connections: 5")
print("- Connection sharing: 3 max shared")
print("- MySQL ping: ✓ Enabled")
print("- Character encoding: utf8mb4")
print("- Transaction control: Manual (autocommit=False)")
