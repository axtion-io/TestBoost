package io.testboost.demo;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/** Deliberately incomplete: `testboost check` must find what it leaves untested. */
class ShippingTest {

    @Test
    void lightParcelPaysTheBasePrice() {
        assertEquals(490, Shipping.costCents(1000, 800, false));
    }

    @Test
    void largeOrdersShipForFree() {
        assertEquals(0, Shipping.costCents(8000, 800, false));
    }
}
