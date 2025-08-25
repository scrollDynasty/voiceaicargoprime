# Эти функции нужно добавить в webhook_server.py или заменить существующие вызовы

async def platform_transfer_call(telephony_session_id, party_id, transfer_to, transfer_type='blind'):
    """Перевести звонок через platform API"""
    try:
        transfer_data = {
            'phoneNumber': transfer_to,
            'transferType': transfer_type
        }
        
        ringcentral_platform.post(
            f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}/transfer',
            transfer_data
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка перевода звонка: {e}")
        return False

async def platform_hangup_call(telephony_session_id, party_id):
    """Завершить звонок через platform API"""
    try:
        ringcentral_platform.delete(
            f'/account/~/extension/~/telephony/sessions/{telephony_session_id}/parties/{party_id}'
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка завершения звонка: {e}")
        return False