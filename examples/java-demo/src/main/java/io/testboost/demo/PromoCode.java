package io.testboost.demo;

import java.util.Locale;

/** Promo codes of the form NAME-PERCENT, e.g. "SPRING-15" (1 to 50 percent). */
public record PromoCode(String name, int percent) {

    public static PromoCode parse(String code) {
        if (code == null) {
            throw new IllegalArgumentException("no code");
        }
        int dash = code.lastIndexOf('-');
        if (dash <= 0 || dash == code.length() - 1) {
            throw new IllegalArgumentException("expected NAME-PERCENT: " + code);
        }
        int percent;
        try {
            percent = Integer.parseInt(code.substring(dash + 1));
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("not a percentage: " + code, e);
        }
        if (percent < 1 || percent > 50) {
            throw new IllegalArgumentException("percent out of range 1-50: " + percent);
        }
        return new PromoCode(code.substring(0, dash).toUpperCase(Locale.ROOT), percent);
    }

    /** Discounted amount, rounded down to the cent. */
    public int apply(int amountCents) {
        return amountCents - amountCents * percent / 100;
    }
}
