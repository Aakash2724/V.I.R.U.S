import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useVirusSocket
 * 
 * Connects to the Python backend via WebSocket.
 * Receives:
 *   - level   → written to levelRef.current (no React re-renders, 30 Hz)
 *   - transcript → fires onTranscript callback
 *   - reply   → fires onReply callback
 *   - status  → fires onStatus callback
 * 
 * Auto-reconnects with exponential backoff.
 */
const getDefaultWsUrl = () => {
    if (typeof window !== 'undefined' && window.location && window.location.host) {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        if (window.location.port === '3000') {
            return `${proto}//${window.location.hostname}:8000/ws`;
        }
        return `${proto}//${window.location.host}/ws`;
    }
    return 'ws://127.0.0.1:8000/ws';
};

export default function useVirusSocket({ 
    url = null, 
    onTranscript, 
    onReply,
    onReplyChunk,
    onReplyEnd,
    onStatus = null,
    onSysMetrics = null,
    onCricketUpdate = null,
    onNewsUpdate = null
} = {}) {
    const levelRef        = useRef(0);
    const [isConnected, setIsConnected] = useState(false);
    const wsRef           = useRef(null);
    const reconnectRef    = useRef(null);
    const backoffRef      = useRef(500);
    const mountedRef      = useRef(true);

    // Keep callbacks in refs to avoid stale closures
    const onTranscriptRef = useRef(onTranscript);
    const onReplyRef      = useRef(onReply);
    const onReplyChunkRef = useRef(onReplyChunk);
    const onReplyEndRef   = useRef(onReplyEnd);
    const onStatusRef     = useRef(onStatus);
    const onSysMetricsRef = useRef(onSysMetrics);
    const onCricketUpdateRef = useRef(onCricketUpdate);
    const onNewsUpdateRef = useRef(onNewsUpdate);

    useEffect(() => { onTranscriptRef.current = onTranscript; }, [onTranscript]);
    useEffect(() => { onReplyRef.current = onReply; }, [onReply]);
    useEffect(() => { onReplyChunkRef.current = onReplyChunk; }, [onReplyChunk]);
    useEffect(() => { onReplyEndRef.current = onReplyEnd; }, [onReplyEnd]);
    useEffect(() => { onStatusRef.current = onStatus; }, [onStatus]);
    useEffect(() => { onSysMetricsRef.current = onSysMetrics; }, [onSysMetrics]);
    useEffect(() => { onCricketUpdateRef.current = onCricketUpdate; }, [onCricketUpdate]);
    useEffect(() => { onNewsUpdateRef.current = onNewsUpdate; }, [onNewsUpdate]);

    const connect = useCallback(() => {
        if (!mountedRef.current) return;

        const targetUrl = url || getDefaultWsUrl();
        const ws = new WebSocket(targetUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log('[VIRUS-WS] Connected');
            backoffRef.current = 500; // reset backoff on success
            if (typeof onStatusRef.current === 'function') {
                onStatusRef.current('connected');
            }
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                switch (msg.type) {
                    case 'level':
                        // Direct ref write — zero React re-renders, blob reads this at 60fps
                        levelRef.current = msg.value;
                        break;

                    case 'transcript':
                        if (typeof onTranscriptRef.current === 'function') {
                            onTranscriptRef.current({ text: msg.value, isFinal: msg.final });
                        }
                        break;

                    case 'reply':
                        if (typeof onReplyRef.current === 'function') {
                            onReplyRef.current(msg.value);
                        }
                        break;
                        
                    case 'reply_chunk':
                        if (typeof onReplyChunkRef.current === 'function') {
                            onReplyChunkRef.current(msg.value);
                        }
                        break;
                        
                    case 'reply_end':
                        if (typeof onReplyEndRef.current === 'function') {
                            onReplyEndRef.current();
                        }
                        break;

                    case 'status':
                        if (typeof onStatusRef.current === 'function') {
                            onStatusRef.current(msg.value);
                        }
                        break;

                    case 'sys_metrics':
                        if (typeof onSysMetricsRef.current === 'function') {
                            onSysMetricsRef.current(msg.value);
                        }
                        break;

                    case 'cricket_update':
                        if (typeof onCricketUpdateRef.current === 'function') {
                            onCricketUpdateRef.current(msg.value);
                        }
                        break;

                    case 'news_update':
                        if (typeof onNewsUpdateRef.current === 'function') {
                            onNewsUpdateRef.current(msg.value);
                        }
                        break;

                    default:
                        break;
                }
            } catch (e) {
                // ignore malformed messages
            }
        };

        ws.onclose = () => {
            console.log('[VIRUS-WS] Disconnected');
            if (typeof onStatusRef.current === 'function') {
                onStatusRef.current('disconnected');
            }
            // Auto-reconnect with exponential backoff
            if (mountedRef.current) {
                const delay = backoffRef.current;
                backoffRef.current = Math.min(delay * 2, 10000);
                reconnectRef.current = setTimeout(connect, delay);
            }
        };

        ws.onerror = () => {
            ws.close(); // triggers onclose → reconnect
        };
    }, [url]);

    useEffect(() => {
        mountedRef.current = true;
        connect();

        // Keep-alive ping every 25 seconds
        const pingInterval = setInterval(() => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send('ping');
            }
        }, 25000);

        return () => {
            mountedRef.current = false;
            clearTimeout(reconnectRef.current);
            clearInterval(pingInterval);
            if (wsRef.current) {
                wsRef.current.onclose = null; // prevent reconnect on intentional close
                wsRef.current.close();
            }
        };
    }, [connect]);

    // Expose method to clear memory sync to backend
    levelRef.clearMemory = useCallback(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send('clear_memory');
        }
    }, []);

    return levelRef;
}
