/**
 * Тестовый скрипт для проверки подключения к RingCentral
 */

require('dotenv').config();
const SDK = require('@ringcentral/sdk').SDK;

async function testConnection() {
    console.log('🧪 Тестирование подключения к RingCentral...\n');
    
    const config = {
        clientId: process.env.RINGCENTRAL_CLIENT_ID,
        clientSecret: process.env.RINGCENTRAL_CLIENT_SECRET,
        jwtToken: process.env.RINGCENTRAL_JWT_TOKEN,
        server: process.env.RINGCENTRAL_SERVER || 'https://platform.ringcentral.com'
    };
    
    console.log('📋 Конфигурация:');
    console.log(`   Client ID: ${config.clientId.substring(0, 10)}...`);
    console.log(`   Server: ${config.server}`);
    console.log(`   JWT Token: ${config.jwtToken ? '✅ Присутствует' : '❌ Отсутствует'}\n`);
    
    try {
        // Создаем SDK
        const rcsdk = new SDK({
            clientId: config.clientId,
            clientSecret: config.clientSecret,
            server: config.server
        });
        
        const platform = rcsdk.platform();
        
        // Авторизация через JWT
        console.log('🔐 Попытка авторизации через JWT...');
        await platform.login({
            jwt: config.jwtToken
        });
        
        console.log('✅ Авторизация успешна!\n');
        
        // Получаем информацию об аккаунте
        console.log('📞 Получение информации об аккаунте...');
        const extensionInfo = await platform.get('/restapi/v1.0/account/~/extension/~');
        const extension = await extensionInfo.json();
        
        console.log('👤 Информация о пользователе:');
        console.log(`   Имя: ${extension.name}`);
        console.log(`   Расширение: ${extension.extensionNumber}`);
        console.log(`   Статус: ${extension.status}`);
        console.log(`   Тип: ${extension.type}\n`);
        
        // Проверяем разрешения
        console.log('🔑 Проверка разрешений...');
        const tokenInfo = await platform.get('/restapi/oauth/tokeninfo');
        const token = await tokenInfo.json();
        
        console.log('📋 Доступные scopes:');
        const scopes = token.scope.split(' ');
        scopes.forEach(scope => {
            console.log(`   - ${scope}`);
        });
        
        // Проверяем возможность получения SIP данных
        console.log('\n🌐 Проверка возможности использования WebPhone...');
        try {
            const sipResponse = await platform.post('/restapi/v1.0/client-info/sip-provision', {
                sipInfo: [{
                    transport: 'WSS'
                }]
            });
            
            const sipData = await sipResponse.json();
            console.log('✅ WebPhone поддерживается!');
            console.log(`   SIP сервер: ${sipData.sipInfo[0].outboundProxy}`);
            console.log(`   Транспорт: ${sipData.sipInfo[0].transport}\n`);
        } catch (error) {
            console.log('❌ WebPhone не поддерживается или недостаточно прав');
            console.log(`   Ошибка: ${error.message}\n`);
        }
        
        console.log('✅ Все тесты пройдены успешно!');
        
    } catch (error) {
        console.error('❌ Ошибка подключения:');
        console.error(`   ${error.message}`);
        
        if (error.response) {
            console.error(`   Статус: ${error.response.status}`);
            console.error(`   Детали: ${JSON.stringify(error.response.data, null, 2)}`);
        }
        
        process.exit(1);
    }
}

// Запуск теста
testConnection();