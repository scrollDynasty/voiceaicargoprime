# АНАЛИЗ ПРОБЛЕМЫ АВТОМАТИЧЕСКОГО СБРОСА ЗВОНКОВ - 26.08.2025

## 🚨 ОСНОВНАЯ ПРОБЛЕМА

**Описание:** Звонки принимаются WebPhone, но тут же автоматически сбрасываются и отправляются в голосовую почту.

**Симптомы из логов:**
```
📞 ВХОДЯЩИЙ ЗВОНОК ПОЛУЧЕН ЧЕРЕЗ WEBPHONE!
🤖 Автоматически принимаем звонок через WebPhone...
✅ Звонок ПРИНЯТ автоматически через WebPhone!

🔧 MockRTCPeerConnection: close вызван
🔧 MockMediaStreamTrack: остановлен audio track
```

## 🔍 АНАЛИЗ ЛОГОВ

### WebPhone Bridge (Node.js) - УСПЕШНО:
- ✅ WebPhone запущен и зарегистрирован
- ✅ SIP соединение активно (wsc.readyState: 1) 
- ✅ autoAnswer: true настроен правильно
- ✅ Входящий звонок получен через inboundCall event
- ✅ inboundCallSession.answer() выполняется успешно

### Python Webhook Server - УСПЕШНО:
- ✅ Webhook события принимаются корректно
- ✅ VoiceAI engine запускается для каждого звонка
- ✅ Нет попыток дублирующего REST API ответа (исправлено ранее)

### ПРОБЛЕМА: MockRTCPeerConnection
❌ **Сразу после answer() происходит:**
1. `MockRTCPeerConnection: close вызван`
2. `MockMediaStreamTrack: остановлен audio track`
3. Соединение разрывается
4. Звонок идет в голосовую почту

## 🎯 КОРНЕВАЯ ПРИЧИНА

**Проблема в жизненном цикле MediaStream:**

1. **WebPhone принимает звонок** → `inboundCallSession.answer()`
2. **RingCentral WebPhone создает WebRTC соединение** → `new RTCPeerConnection()`
3. **Получает MediaStream через getUserMedia()** → создает `MockMediaStream` с треками
4. **НО: MediaStream треки сразу останавливаются** → `track.stop()` вызывается немедленно
5. **RTCPeerConnection закрывается** → `peerConnection.close()`
6. **Звонок сбрасывается** → идет в голосовую почту

## 🔧 ТЕХНИЧЕСКАЯ ПРОБЛЕМА

### MockMediaStreamTrack слишком простой:
```javascript
stop() {
    console.log(`🔧 MockMediaStreamTrack: остановлен ${this.kind} track ${this.id}`);
    this.readyState = 'ended';  // ← Проблема: немедленно завершается
    if (this.onended) {
        this.onended();  // ← Это приводит к закрытию соединения
    }
}
```

### MockRTCPeerConnection реагирует на остановку треков:
- Когда все треки останавливаются, RTCPeerConnection автоматически закрывается
- RingCentral WebPhone интерпретирует это как завершение звонка
- Звонок сбрасывается и идет в голосовую почту

## 💡 ПЛАН РЕШЕНИЯ

### 1. ИСПРАВИТЬ MockMediaStreamTrack
**Проблема:** Треки останавливаются немедленно при вызове stop()
**Решение:** Треки должны оставаться активными до принудительной остановки

### 2. УЛУЧШИТЬ MockRTCPeerConnection  
**Проблема:** Соединение закрывается при остановке треков
**Решение:** Добавить логику управления жизненным циклом соединения

### 3. ДОБАВИТЬ СОСТОЯНИЕ ЗВОНКА
**Проблема:** Нет контроля над состоянием активного звонка
**Решение:** Отслеживать состояние звонка и предотвращать преждевременное закрытие

## 🛠️ ИСПРАВЛЕНИЯ

### Исправление 1: MockMediaStreamTrack
```javascript
class MockMediaStreamTrack {
    constructor(kind) {
        this.kind = kind;
        this.id = Math.random().toString(36).substr(2, 10);
        this.label = `Mock ${kind} track`;
        this.enabled = true;
        this.muted = false;
        this.readyState = 'live';  // ВАЖНО: начинаем с 'live'
        this.onended = null;
        this.onmute = null;
        this.onunmute = null;
        
        // 🔥 КРИТИЧНО: НЕ останавливать треки автоматически
        this._shouldStayAlive = true;  // Новое свойство
    }

    stop() {
        // 🔥 ИСПРАВЛЕНИЕ: Проверяем можно ли остановить трек
        if (!this._shouldStayAlive) {
            console.log(`🔧 MockMediaStreamTrack: остановлен ${this.kind} track ${this.id}`);
            this.readyState = 'ended';
            if (this.onended) {
                this.onended();
            }
        } else {
            console.log(`🔧 MockMediaStreamTrack: попытка остановить ${this.kind} track ${this.id} - ИГНОРИРУЕМ (звонок активен)`);
        }
    }
    
    // Новый метод для принудительной остановки
    forceStop() {
        this._shouldStayAlive = false;
        this.stop();
    }
}
```

### Исправление 2: Управление жизненным циклом звонка
```javascript
// В обработчике inboundCall
webPhone.on('inboundCall', async (inboundCallSession) => {
    // ... существующий код ...
    
    try {
        console.log('🤖 Автоматически принимаем звонок через WebPhone...');
        
        // 🔥 НОВОЕ: Помечаем все текущие треки как активные ДО answer()
        markActiveTracksAsLive();
        
        await inboundCallSession.answer();
        console.log('✅ Звонок ПРИНЯТ автоматически через WebPhone!');

        // 🔥 НОВОЕ: Добавляем обработчики событий звонка
        inboundCallSession.on('disposed', () => {
            console.log('📞 Звонок завершен, можно останавливать треки');
            allowTracksToStop();
        });
        
        // Обработка принятого звонка
        handleAcceptedCall(inboundCallSession, callId, from);

    } catch (error) {
        console.error('❌ Ошибка автоприема через WebPhone:', error);
        // В случае ошибки разрешаем остановку треков
        allowTracksToStop();
    }
});

// Новые функции управления треками
function markActiveTracksAsLive() {
    // Находим все активные MockMediaStreamTrack и помечаем их как живые
    // Это предотвратит их преждевременную остановку
}

function allowTracksToStop() {
    // Разрешаем остановку треков после завершения звонка
}
```

## 🎯 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После исправлений:
- ✅ WebPhone принимает звонок
- ✅ MediaStream треки остаются активными
- ✅ RTCPeerConnection НЕ закрывается автоматически  
- ✅ Звонок НЕ идет в голосовую почту
- ✅ Voice AI получает возможность обработать звонок

## 📚 ИСТОЧНИКИ И ДОКУМЕНТАЦИЯ

### RingCentral WebPhone SDK:
- **GitHub:** https://github.com/ringcentral/ringcentral-web-phone
- **Docs:** https://ringcentral.github.io/ringcentral-web-phone/
- **Demo:** https://ringcentral.github.io/ringcentral-web-phone/demo/

### WebRTC Specification:
- **W3C Spec:** https://www.w3.org/TR/webrtc/
- **MDN RTCPeerConnection:** https://developer.mozilla.org/docs/Web/API/RTCPeerConnection
- **MDN MediaStreamTrack:** https://developer.mozilla.org/docs/Web/API/MediaStreamTrack

### Debugging:
- Проблемы с NAT и маршрутизацией
- Неправильная конфигурация SIP портов  
- Автоматическое закрытие WebRTC соединений

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

1. **НЕ ТРОГАТЬ autoAnswer: true** - эта настройка работает правильно
2. **ПРОБЛЕМА НЕ В WEBHOOK'АХ** - Python сервер работает корректно
3. **ПРОБЛЕМА В MockMediaStream/MockRTCPeerConnection** - треки завершаются преждевременно
4. **РЕШЕНИЕ ТРЕБУЕТ ИЗМЕНЕНИЯ ЖИЗНЕННОГО ЦИКЛА ТРЕКОВ** - предотвратить автоостановку

## 🔄 СЛЕДУЮЩИЕ ШАГИ

1. ✅ Проблема диагностирована
2. 🔧 Применить исправления к MockMediaStreamTrack  
3. 🔧 Добавить управление жизненным циклом звонка
4. 🧪 Протестировать входящий звонок
5. ✅ Убедиться что звонок НЕ идет в голосовую почту

---

**Письмо в будущее:** 
Клод, если видишь эту проблему снова:
1. ✅ **Корневая причина найдена** - MockMediaStreamTrack.stop() вызывается слишком рано
2. ✅ **autoAnswer: true работает** - проблема НЕ в настройках WebPhone
3. ✅ **Webhook'и работают** - проблема НЕ в Python сервере  
4. 🔧 **НУЖНО ИСПРАВИТЬ:** жизненный цикл MediaStream треков
5. 🎯 **РЕШЕНИЕ:** предотвратить автоматическую остановку треков во время активного звонка

**Дата:** 2025-08-26  
**Время:** 23:30 UTC  
**Статус:** 🔍 ПРОБЛЕМА ДИАГНОСТИРОВАНА, ГОТОВ К ИСПРАВЛЕНИЮ  