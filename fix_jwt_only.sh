#!/bin/bash

echo "🔧 Fixing RingCentral to use JWT only..."

# 1. Backup files
cp /workspace/webhook_server.py /workspace/webhook_server.py.backup

# 2. Fix transfer_call in webhook_server.py
sed -i '321,327s/.*/            try:\
                transfer_data = {\
                    "phoneNumber": transfer_to,\
                    "transferType": transfer_type\
                }\
                \
                ringcentral_platform.post(\
                    f"\/account\/~\/extension\/~\/telephony\/sessions\/{call_data[\"telephonySessionId\"]}\/parties\/{call_data[\"partyId\"]}\/transfer",\
                    transfer_data\
                )\
                success = True\
            except Exception as e:\
                logger.error(f"Ошибка перевода звонка: {e}")\
                success = False/' /workspace/webhook_server.py

# 3. Fix hangup_call in webhook_server.py  
sed -i '356,360s/.*/            try:\
                ringcentral_platform.delete(\
                    f"\/account\/~\/extension\/~\/telephony\/sessions\/{call_data[\"telephonySessionId\"]}\/parties\/{call_data[\"partyId\"]}"\
                )\
                success = True\
            except Exception as e:\
                logger.error(f"Ошибка завершения звонка: {e}")\
                success = False/' /workspace/webhook_server.py

# 4. Remove test_auth.py
rm -f /workspace/test_auth.py

echo "✅ JWT-only authentication setup complete!"
echo "📝 Check webhook_server.py for any remaining issues"
