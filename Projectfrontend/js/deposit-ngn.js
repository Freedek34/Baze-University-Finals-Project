/**
 * CryptoVault - Buy with NGN (card demo)
 */
const RATES = { USDT: 1620, BTC: 110500000, ETH: 5830000 };
let purchaseRequestId = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;

    document.getElementById('buyCoin')?.addEventListener('change', updateEstimate);
    document.getElementById('fiatAmount')?.addEventListener('input', updateEstimate);
    document.getElementById('payBtn')?.addEventListener('click', processPayment);

    document.getElementById('cardNumber')?.addEventListener('input', (e) => {
        let v = e.target.value.replace(/\D/g, '').slice(0, 16);
        e.target.value = v.replace(/(.{4})/g, '$1 ').trim();
    });
    document.getElementById('cardExpiry')?.addEventListener('input', (e) => {
        let v = e.target.value.replace(/\D/g, '').slice(0, 4);
        if (v.length >= 2) v = v.slice(0, 2) + '/' + v.slice(2);
        e.target.value = v;
    });
});

function updateEstimate() {
    const coin = document.getElementById('buyCoin').value;
    const fiat = parseFloat(document.getElementById('fiatAmount').value) || 0;
    const rate = RATES[coin] || 1620;
    const crypto = fiat > 0 ? (fiat / rate) : 0;
    const el = document.getElementById('cryptoEstimate');
    if (el) el.textContent = crypto > 0 ? Utils.formatCrypto(crypto, coin === 'USDT' ? 2 : 6) + ' ' + coin : '—';
}

async function processPayment() {
    const coin = document.getElementById('buyCoin').value;
    const fiatAmount = parseFloat(document.getElementById('fiatAmount').value);
    const cardNumber = document.getElementById('cardNumber').value.replace(/\s/g, '');
    const expiry = document.getElementById('cardExpiry').value;
    const cvv = document.getElementById('cardCvv').value;

    if (!fiatAmount || fiatAmount < 1000) { Utils.showError('Minimum purchase is ₦1,000'); return; }
    if (cardNumber.length < 16) { Utils.showError('Enter a valid card number'); return; }
    if (!expiry || expiry.length < 4) { Utils.showError('Enter card expiry'); return; }
    if (!cvv || cvv.length < 3) { Utils.showError('Enter CVV'); return; }

    const modal = document.getElementById('processingModal');
    modal.classList.add('active');
    Utils.setBtnLoading('#payBtn');

    try {
        const init = await API.initFiatPurchase(coin, fiatAmount, cardNumber);
        purchaseRequestId = init.request_id;
        await new Promise(r => setTimeout(r, 2000));
        const result = await API.completeFiatPurchase(purchaseRequestId);
        modal.classList.remove('active');
        document.getElementById('formSection').style.display = 'none';
        document.getElementById('successSection').style.display = 'block';
        document.getElementById('successMessage').textContent =
            `${Utils.formatAmount(result.amount, result.coin)} credited. Reference: ${result.reference}`;
        Utils.showSuccess('Purchase complete!');
    } catch (e) {
        modal.classList.remove('active');
        Utils.showError(e.message);
    } finally {
        Utils.setBtnLoading('#payBtn', false);
    }
}
