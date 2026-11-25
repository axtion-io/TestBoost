package io.testboost.demo;

/** Shipping cost of an order, in cents. */
public final class Shipping {

    /** Orders from this amount ship for free (standard delivery only). */
    public static final int FREE_FROM_CENTS = 5000;
    static final int BASE_CENTS = 490;
    static final int PER_EXTRA_500G_CENTS = 150;

    private Shipping() {
    }

    /**
     * Standard delivery: 4.90 up to 1 kg, then 1.50 per started 500 g; free from 50.00.
     * Express: twice the standard price, never free.
     */
    public static int costCents(int orderCents, int weightGrams, boolean express) {
        if (orderCents < 0 || weightGrams <= 0) {
            throw new IllegalArgumentException("order amount must be >= 0 and weight > 0");
        }
        if (!express && orderCents >= FREE_FROM_CENTS) {
            return 0;
        }
        int extraSteps = weightGrams <= 1000 ? 0 : (weightGrams - 1000 + 499) / 500;
        int standard = BASE_CENTS + extraSteps * PER_EXTRA_500G_CENTS;
        return express ? standard * 2 : standard;
    }
}
