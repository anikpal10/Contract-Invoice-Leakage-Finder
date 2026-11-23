export const REVIEW_REQUIRED_CURRENCY = 'REVIEW_REQUIRED';

export const getCurrencySymbol = (code?: string | null) => {
    const c = (code || '').toUpperCase();
    switch (c) {
        case 'INR':
            return '₹';
        case 'GBP':
            return '£';
        case 'USD':
            return '$';
        case 'EUR':
            return '€';
        case 'CAD':
            return 'C$';
        case 'AUD':
            return 'A$';
        case 'JPY':
            return '¥';
        default:
            return c ? `${c} ` : '';
    }
};

export const renderMoney = (amount: number, currency?: string | null) => {
    const num = Number(amount || 0);
    const code = (currency || '').trim().toUpperCase();
    if (!code || code === 'NONE' || code === REVIEW_REQUIRED_CURRENCY) {
        return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return `${getCurrencySymbol(code)}${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const aggregateByCurrency = (items: Array<{ currency?: string | null; amount: number }>) => {
    const out: Record<string, number> = {};
    for (const it of items) {
        const c = (it.currency || '').trim().toUpperCase();
        if (!c) continue;
        out[c] = (out[c] || 0) + Number(it.amount || 0);
    }
    return out;
};

export const formatBreakdown = (breakdown?: Record<string, number> | null) => {
    const b = breakdown || {};
    const keys = Object.keys(b).filter(k => k && k !== 'NONE');
    if (!keys.length) return '0.00';
    return keys
        .sort()
        .map((k) => {
            const sym = getCurrencySymbol(k);
            const val = Number(b[k] || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            if (k === REVIEW_REQUIRED_CURRENCY) {
                return val;
            }
            return sym ? `${sym}${val}` : `${k} ${val}`;
        })
        .join(' | ');
};
