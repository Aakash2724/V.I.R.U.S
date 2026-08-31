import { useEffect, useRef } from 'react';

/**
 * useSharedMic
 * 
 * Owns the single getUserMedia call for the PlasmaBlob visualizer.
 * Returns only the levelRef.
 */
export default function useSharedMic({ sensitivity = 0.2 } = {}) {
    const levelRef          = useRef(0);
    const sensitivityRef    = useRef(sensitivity);
    const streamRef         = useRef(null);
    const audioCtxRef       = useRef(null);
    const analyserRef       = useRef(null);
    const rafRef            = useRef(null);

    // Keep sensitivity in sync
    useEffect(() => { sensitivityRef.current = sensitivity; }, [sensitivity]);

    useEffect(() => {
        let destroyed = false;

        async function startAnalyser() {
            try {
                // Disable audio processing to prevent Windows from locking the mic in Exclusive Mode!
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: false,
                        noiseSuppression: false,
                        autoGainControl: false
                    }, 
                    video: false 
                });
                if (destroyed) { stream.getTracks().forEach(t => t.stop()); return; }
                streamRef.current = stream;

                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioCtx();
                audioCtxRef.current = ctx;

                // Resume on first user interaction (Chrome autoplay policy)
                const unlock = () => { if (ctx.state === 'suspended') ctx.resume(); window.removeEventListener('click', unlock); };
                window.addEventListener('click', unlock);

                const source  = ctx.createMediaStreamSource(stream);
                const analyser = ctx.createAnalyser();
                analyser.fftSize = 1024;
                analyser.smoothingTimeConstant = 0.80; 
                source.connect(analyser);
                analyserRef.current = analyser;

                const data = new Uint8Array(analyser.frequencyBinCount);

                const tick = () => {
                    if (destroyed || !analyserRef.current) return;
                    analyser.getByteFrequencyData(data);

                    // RMS energy
                    let sumSquares = 0;
                    for (let i = 0; i < data.length; i++) {
                        const norm = data[i] / 255.0;
                        sumSquares += norm * norm;
                    }
                    const rms = Math.sqrt(sumSquares / data.length);

                    const sens   = sensitivityRef.current || 0.2;
                    const target = Math.min(0.25, Math.pow(rms * 5.0 * sens, 0.85));

                    const prev  = levelRef.current;
                    const alpha = target > prev ? 0.04 : 0.18;
                    levelRef.current = prev + (target - prev) * alpha;

                    rafRef.current = requestAnimationFrame(tick);
                };
                tick();

            } catch (err) {
                console.warn('[useSharedMic] Mic unavailable:', err.message);
            }
        }

        startAnalyser();

        // ── CLEANUP ────────────────────────────────────────────────────────
        return () => {
            destroyed = true;

            cancelAnimationFrame(rafRef.current);

            if (streamRef.current) {
                streamRef.current.getTracks().forEach(t => t.stop());
                streamRef.current = null;
            }

            if (audioCtxRef.current) {
                audioCtxRef.current.close();
                audioCtxRef.current = null;
            }

            analyserRef.current  = null;
            levelRef.current     = 0;
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return levelRef; 
}
