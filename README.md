# BuildQuality Professional Library — Material Calculator

Professional Flask quality library with:

- Codes, Materials, Quality Document Template, Method Statement, Test Reports, and Batch Plant libraries.
- Administrator-only add, edit, delete, and user management.
- One-time 7-day free trial.
- Monthly/yearly subscription controls.
- Moyasar server-side payment verification restricted to Mada cards.
- Material consumption and cost calculator.

## Material calculation

For resources in the `Materials` category, the administrator enters:

- Material Type
- Consumption Rate (kg/m²)
- Price per kg (SAR)
- Online datasheet/resource URL

The library calculates:

- Required Quantity = Area × Consumption Rate
- Total Cost = Required Quantity × Price per kg

Multiple materials can be selected and totalled in one report.

## Render

Build command:

    pip install -r requirements.txt

Start command:

    gunicorn server:app

The included `Procfile` already contains the correct start command.

## Database migration

At startup the application safely adds these columns to an existing `link_item` table:

- `material_type`
- `consumption_rate`
- `price_per_kg`

Existing users, payments, subscriptions, trials, and resources are retained.
