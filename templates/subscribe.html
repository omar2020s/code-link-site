{% extends "base.html" %}
{% block title %}Subscription Plans{% endblock %}
{% block content %}
<section class="page-heading">
    <div>
        <span class="eyebrow">Continue your access</span>
        <h1>Choose Your Subscription Plan</h1>
        {% if current_user.has_active_trial %}
            <p>Your free trial is active. You can subscribe now without losing the remaining {{ current_user.trial_days_left }} trial day(s).</p>
        {% elif current_user.has_active_subscription %}
            <p>Your paid subscription is active. Renewing now adds the new period to your existing expiration date.</p>
        {% else %}
            <p>Your free trial has ended. Complete a successful Saudi Mada payment to continue using the protected library.</p>
        {% endif %}
    </div>
    {% if current_user.is_authenticated %}
    <div class="status-card {% if current_user.has_library_access %}active{% endif %}">
        <span>Access Status</span>
        <strong>
            {% if current_user.is_admin %}
                Administrator — Permanent Access
            {% elif current_user.has_active_subscription %}
                Active Paid Subscription
            {% elif current_user.has_active_trial %}
                Free Trial — {{ current_user.trial_days_left }} day(s) remaining
            {% else %}
                Trial Ended — Subscription Required
            {% endif %}
        </strong>
        {% if current_user.has_active_subscription and current_user.subscription_end %}
            <small>Paid access expires on {{ current_user.subscription_end.strftime('%Y-%m-%d') }}</small>
        {% elif current_user.has_active_trial and current_user.trial_end %}
            <small>Free trial expires on {{ current_user.trial_end.strftime('%Y-%m-%d %H:%M') }} UTC</small>
        {% endif %}
    </div>
    {% endif %}
</section>

{% if not configured %}
<div class="alert warning">Setup mode: add MOYASAR_PUBLISHABLE_KEY and MOYASAR_SECRET_KEY to your environment variables before accepting payments.</div>
{% endif %}

<div class="mada-notice">
    <div class="mada-logo-text">mada</div>
    <div><strong>Mada cards only</strong><span>Payments are processed securely by Moyasar in Saudi Riyals.</span></div>
</div>

<section class="pricing-grid">
    {% for plan in plans.values() %}
    <article class="price-card {% if plan.code == 'yearly' %}featured{% endif %}">
        <span class="plan-badge">{{ plan.badge }}</span>
        <h2>{{ plan.name }}</h2>
        <div class="price">{{ money_sar(plan.price_halalas) }}</div>
        <ul class="clean-list">
            <li>Full access to the protected link library</li>
            <li>Search by category, title, keywords, notes, and URL</li>
            <li>Unused free-trial time is preserved when subscribing early</li>
            <li>Renewal time is added to active paid access</li>
            <li>{{ plan.days }} paid days of access</li>
            <li>Secure Saudi Mada card payment</li>
        </ul>
        <a class="btn primary full large {% if not configured %}disabled{% endif %}" href="{{ url_for('checkout', plan_code=plan.code) }}">Pay with Mada</a>
    </article>
    {% endfor %}
</section>

<div class="card note-card">
    <strong>Payment security:</strong> Card details are entered directly in the Moyasar payment form and are not stored by this website. After payment, the server checks the payment status, amount, currency, account metadata, checkout token, and confirms that the card network is Mada before activating paid access.
</div>
{% endblock %}
