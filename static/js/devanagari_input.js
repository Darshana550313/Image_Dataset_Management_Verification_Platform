(function () {
    const selector = 'input[name*="marathi_name"], input[name*="hindi_name"]';
    const overrides = {
        marathi: {
            banana: 'केळी', keli: 'केळी', rajapuri: 'राजापुरी', rajapurii: 'राजापुरी',
            mango: 'आंबा', amba: 'आंबा', apple: 'सफरचंद', neem: 'निंब', tulsi: 'तुळस',
            ashwagandha: 'अश्वगंधा', aloevera: 'कोरफड', aloe: 'कोरफड', guava: 'पेरू',
            papaya: 'पपई', turmeric: 'हळद', ginger: 'आले', onion: 'कांदा', potato: 'बटाटा',
            tomato: 'टोमॅटो', carrot: 'गाजर', rose: 'गुलाब', hibiscus: 'जास्वंद'
        },
        hindi: {
            banana: 'केला', keli: 'केला', rajapuri: 'राजापुरी', rajapurii: 'राजापुरी',
            mango: 'आम', amba: 'आम', apple: 'सेब', neem: 'नीम', tulsi: 'तुलसी',
            ashwagandha: 'अश्वगंधा', aloevera: 'घृतकुमारी', aloe: 'घृतकुमारी', guava: 'अमरूद',
            papaya: 'पपीता', turmeric: 'हल्दी', ginger: 'अदरक', onion: 'प्याज', potato: 'आलू',
            tomato: 'टमाटर', carrot: 'गाजर', rose: 'गुलाब', hibiscus: 'गुड़हल'
        }
    };
    const consonants = {
        ksh: 'क्ष', dny: 'ज्ञ', gny: 'ज्ञ', gy: 'ज्ञ', shr: 'श्र', tr: 'त्र',
        chh: 'छ', kh: 'ख', gh: 'घ', ch: 'च', jh: 'झ', th: 'थ', dh: 'ध',
        ph: 'फ', bh: 'भ', sh: 'श', k: 'क', g: 'ग', c: 'क', j: 'ज',
        t: 'त', d: 'द', n: 'न', p: 'प', b: 'ब', m: 'म', y: 'य',
        r: 'र', l: 'ल', v: 'व', w: 'व', s: 'स', h: 'ह'
    };
    const signs = { aa: 'ा', ee: 'ी', ii: 'ी', oo: 'ू', uu: 'ू', ai: 'ै', au: 'ौ', a: '', i: 'ि', u: 'ु', e: 'े', o: 'ो' };
    const vowels = { aa: 'आ', ee: 'ई', ii: 'ई', oo: 'ऊ', uu: 'ऊ', ai: 'ऐ', au: 'औ', a: 'अ', i: 'इ', u: 'उ', e: 'ए', o: 'ओ' };
    const consonantKeys = Object.keys(consonants).sort((a, b) => b.length - a.length);
    const vowelKeys = Object.keys(signs).sort((a, b) => b.length - a.length);
    let activeInput = null;
    let keyboard = null;

    function languageFor(input) {
        return (input.name || '').includes('hindi') ? 'hindi' : 'marathi';
    }

    function romanWord(word, language) {
        const lower = word.toLowerCase();
        const known = overrides[language][lower] || overrides.marathi[lower];
        if (known) return known;

        let out = '';
        let i = 0;
        while (i < lower.length) {
            const con = consonantKeys.find(key => lower.startsWith(key, i));
            if (con) {
                out += consonants[con];
                i += con.length;
                const vowel = vowelKeys.find(key => lower.startsWith(key, i));
                if (vowel) {
                    out += signs[vowel];
                    i += vowel.length;
                }
                continue;
            }
            const vowel = vowelKeys.find(key => lower.startsWith(key, i));
            if (vowel) {
                out += vowels[vowel];
                i += vowel.length;
                continue;
            }
            out += word[i];
            i += 1;
        }
        return out;
    }

    function convert(input, rawValue) {
        const source = rawValue || input.dataset.rawRomanValue || input.value;
        if (!/[A-Za-z]/.test(source)) return;
        const language = languageFor(input);
        input.value = source.replace(/[A-Za-z]+/g, word => romanWord(word, language));
    }

    function insertText(input, text) {
        const start = input.selectionStart || input.value.length;
        const end = input.selectionEnd || input.value.length;
        input.value = input.value.slice(0, start) + text + input.value.slice(end);
        const next = start + text.length;
        input.focus();
        input.setSelectionRange(next, next);
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function backspace(input) {
        const start = input.selectionStart || input.value.length;
        const end = input.selectionEnd || input.value.length;
        if (start !== end) {
            input.value = input.value.slice(0, start) + input.value.slice(end);
            input.setSelectionRange(start, start);
        } else if (start > 0) {
            input.value = input.value.slice(0, start - 1) + input.value.slice(start);
            input.setSelectionRange(start - 1, start - 1);
        }
        input.focus();
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function ensureKeyboard() {
        if (keyboard) return keyboard;
        keyboard = document.createElement('div');
        keyboard.style.cssText = 'position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9999;max-width:min(760px,94vw);background:#fff;border:1px solid #cbd5e1;border-radius:12px;box-shadow:0 12px 30px rgba(15,23,42,.18);padding:10px;display:none;gap:6px;flex-wrap:wrap;';
        const keys = ['अ','आ','इ','ई','उ','ऊ','ए','ऐ','ओ','औ','क','ख','ग','घ','च','छ','ज','झ','ट','ठ','ड','ढ','त','थ','द','ध','न','प','फ','ब','भ','म','य','र','ल','व','श','ष','स','ह','ळ','क्ष','ज्ञ','त्र','ं','ः','्','ा','ि','ी','ु','ू','े','ै','ो','ौ','Space','Back','Close'];
        keys.forEach(key => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = key;
            button.style.cssText = 'border:1px solid #e2e8f0;background:#f8fafc;border-radius:8px;padding:7px 10px;font:600 14px Arial;cursor:pointer;';
            button.addEventListener('mousedown', event => event.preventDefault());
            button.addEventListener('click', () => {
                if (!activeInput) return;
                if (key === 'Close') keyboard.style.display = 'none';
                else if (key === 'Back') backspace(activeInput);
                else if (key === 'Space') insertText(activeInput, ' ');
                else insertText(activeInput, key);
            });
            keyboard.appendChild(button);
        });
        document.body.appendChild(keyboard);
        return keyboard;
    }

    function attach() {
        document.querySelectorAll(selector).forEach(input => {
            input.setAttribute('lang', languageFor(input) === 'hindi' ? 'hi' : 'mr');
            input.setAttribute('autocomplete', 'off');
            if (input.dataset.devanagariInputReady === 'on') return;
            input.dataset.devanagariInputReady = 'on';
            input.addEventListener('focus', () => {
                activeInput = input;
                ensureKeyboard().style.display = 'flex';
            });
            input.addEventListener('input', () => {
                input.dataset.rawRomanValue = input.value;
            });
            input.addEventListener('blur', () => {
                setTimeout(() => {
                    if (!keyboard || !keyboard.matches(':hover')) convert(input, input.dataset.rawRomanValue || input.value);
                }, 0);
            });
            input.addEventListener('keydown', event => {
                if (event.key === ' ' || event.key === 'Enter') {
                    const raw = input.value;
                    setTimeout(() => convert(input, raw), 0);
                }
            });
        });
    }

    document.addEventListener('submit', event => {
        event.target.querySelectorAll(selector).forEach(input => {
            convert(input, input.dataset.rawRomanValue || input.value);
        });
    }, true);

    attach();
    new MutationObserver(attach).observe(document.documentElement, { childList: true, subtree: true });
})();
