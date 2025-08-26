/**
 * Простой тест статуса WebPhone регистрации
 */

require('dotenv').config();
const SDK = require('@ringcentral/sdk').SDK;
const WebPhone = require('ringcentral-web-phone').default;

// WebSocket полифилл для Node.js
global.WebSocket = require('ws');

// Navigator полифилл для Node.js
global.navigator = global.navigator || {
    userAgent: 'RingCentral-WebPhone-Bridge/1.0.0 (Node.js)',
    appName: 'RingCentral WebPhone Bridge',
    appVersion: '1.0.0'
};

const config = {
    clientId: process.env.RINGCENTRAL_CLIENT_ID,
    clientSecret: process.env.RINGCENTRAL_CLIENT_SECRET,
    jwtToken: process.env.RINGCENTRAL_JWT_TOKEN,
    server: process.env.RINGCENTRAL_SERVER
};

async function testWebPhoneRegistration() {
    console.log('🔍 Тестирование регистрации WebPhone...\n');
    
    try {
        // Инициализация SDK
        console.log('1. Инициализация RingCentral SDK...');
        const rcsdk = new SDK({
            server: config.server,
            clientId: config.clientId,
            clientSecret: config.clientSecret
        });
        
        const platform = rcsdk.platform();
        await platform.login({ jwt: config.jwtToken });
        console.log('✅ RingCentral SDK инициализирован\n');
        
        // Получение SIP данных
        console.log('2. Получение SIP данных...');
        const response = await platform.post('/restapi/v1.0/client-info/sip-provision', {
            sipInfo: [{ transport: 'WSS' }]
        });
        const sipProvisionData = await response.json();
        const sipInfo = sipProvisionData.sipInfo[0];
        console.log(`✅ SIP данные получены: ${sipInfo.username}@${sipInfo.domain}\n`);
        
        // Создание WebPhone
        console.log('3. Создание WebPhone...');
        const webPhone = new WebPhone({
            sipInfo: sipInfo,
            userAgent: 'RingCentral-WebPhone-Test/1.0.0',
            logLevel: 1
        });
        
        console.log('✅ WebPhone создан\n');
        
        // Обработчики событий
        let registrationAttempted = false;
        let registrationSuccessful = false;
        
        webPhone.on('registering', () => {
            registrationAttempted = true;
            console.log('🔄 WebPhone пытается зарегистрироваться...');
        });
        
        webPhone.on('registered', () => {
            registrationSuccessful = true;
            console.log('✅ WebPhone успешно зарегистрирован!');
        });
        
        webPhone.on('registrationFailed', (error) => {
            console.log('❌ Ошибка регистрации:', error);
        });
        
        // Запуск WebPhone
        console.log('4. Запуск WebPhone...');
        await webPhone.start();
        console.log('✅ WebPhone запущен');
        
        // Принудительная регистрация
        console.log('4.1. Принудительная регистрация...');
        if (webPhone.sipClient && webPhone.sipClient.register) {
            await webPhone.sipClient.register();
            console.log('✅ Регистрация инициирована\n');
        } else {
            console.log('⚠️ Метод register не найден\n');
        }
        
        // Ожидание результата
        console.log('5. Ожидание результата регистрации (30 секунд)...');
        
        for (let i = 0; i < 30; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            if (registrationSuccessful) {
                console.log('🎉 УСПЕХ: WebPhone зарегистрирован!');
                process.exit(0);
            }
            
            if (i % 5 === 0) {
                console.log(`⏰ Ожидание... ${30 - i} секунд осталось`);
            }
        }
        
        if (registrationAttempted) {
            console.log('⚠️ Регистрация была инициирована, но не завершена за 30 секунд');
        } else {
            console.log('❌ Регистрация не была инициирована');
        }
        
        // Завершение
        if (webPhone.sipClient && webPhone.sipClient.stop) {
            await webPhone.sipClient.stop();
        }
        
    } catch (error) {
        console.error('❌ Ошибка:', error.message);
        process.exit(1);
    }
}

testWebPhoneRegistration();