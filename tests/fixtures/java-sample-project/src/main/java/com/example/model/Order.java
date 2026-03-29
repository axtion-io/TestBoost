package com.example.model;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "orders")
public class Order {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private Long userId;
    private BigDecimal amount;

    public Order() {}

    public Order(Long userId, BigDecimal amount) {
        this.userId = userId;
        this.amount = amount;
    }

    public Long getId() { return id; }
    public Long getUserId() { return userId; }
    public BigDecimal getAmount() { return amount; }
}
