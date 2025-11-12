#!/usr/bin/env python3
"""
Production Deployment Script
Run this on your Render server to deploy personalized member chat
"""

import os
import sys
import shutil
from datetime import datetime

def backup_existing_files():
    """Backup existing files before deployment"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    files_to_backup = [
        "webhook_handlers.py",
        "app/prompts.py"
    ]
    
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup_{timestamp}"
            shutil.copy2(file_path, backup_path)
            print(f"✅ Backed up {file_path} → {backup_path}")

def deploy_personalized_system():
    """Deploy the personalized member chat system"""
    
    print("🚀 DEPLOYING PERSONALIZED MEMBER CHAT SYSTEM")
    print("="*50)
    
    # 1. Backup files
    print("\n1. Creating backups...")
    backup_existing_files()
    
    # 2. Initialize database tables
    print("\n2. Initializing database tables...")
    try:
        from scripts.integrate_personalized_prompting import MemberPersonalityManager
        manager = MemberPersonalityManager()
        print("✅ Database tables ready")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    
    # 3. Load existing member profiles
    print("\n3. Loading member profiles...")
    try:
        from scripts.add_staaci_personality import add_staaci_to_database
        from scripts.integrate_personalized_prompting import create_sabrina_demo_profile
        
        create_sabrina_demo_profile()
        add_staaci_to_database()
        print("✅ Member profiles loaded")
    except Exception as e:
        print(f"❌ Profile loading failed: {e}")
        return False
    
    # 4. Test system
    print("\n4. Testing personalized system...")
    try:
        manager = MemberPersonalityManager()
        
        # Test Sabrina
        sabrina_personality = manager.get_member_personality('sabrina')
        if sabrina_personality:
            print("✅ Sabrina's profile loaded successfully")
        
        # Test StaaCi  
        staaci_personality = manager.get_member_personality('staaci')
        if staaci_personality:
            print("✅ StaaCi's profile loaded successfully")
            
    except Exception as e:
        print(f"❌ System test failed: {e}")
        return False
    
    print("\n🎉 DEPLOYMENT SUCCESSFUL!")
    print("\n📋 Next Steps:")
    print("- Monitor logs for personalized prompt usage")
    print("- Test with real member conversations")  
    print("- Watch for automatic profile creation")
    print("- System will learn and improve over time")
    
    return True

if __name__ == "__main__":
    deploy_personalized_system()
