-- Mancino retail analytics prototype
-- DDL only: creates the schema and normalized tables for the selected source files.
-- No source data is loaded by this script.

CREATE DATABASE IF NOT EXISTS mancino_analytics
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE mancino_analytics;

CREATE TABLE IF NOT EXISTS stores (
    store_id    INT UNSIGNED NOT NULL,
    store_name  VARCHAR(120) NOT NULL,
    neighborhood VARCHAR(80),
    address     VARCHAR(200),
    city        VARCHAR(80),
    state       CHAR(2),
    zip         VARCHAR(10),
    latitude    DECIMAL(9, 6),
    longitude   DECIMAL(9, 6),
    PRIMARY KEY (store_id)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS products (
    product_id   VARCHAR(16) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    brand        VARCHAR(120),
    category     VARCHAR(100) NOT NULL,
    subcategory  VARCHAR(100),
    unit_size    VARCHAR(80),
    price        DECIMAL(10, 2),
    unit_cost    DECIMAL(10, 2),
    PRIMARY KEY (product_id),
    INDEX idx_products_category_subcategory (category, subcategory)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(32) NOT NULL,
    customer_id    VARCHAR(16),
    store_id       INT UNSIGNED NOT NULL,
    txn_ts         DATETIME NOT NULL,
    subtotal       DECIMAL(12, 2),
    tax            DECIMAL(12, 2),
    total          DECIMAL(12, 2),
    num_items      SMALLINT UNSIGNED,
    payment_type   VARCHAR(40),
    day_name       VARCHAR(12),
    PRIMARY KEY (transaction_id),
    INDEX idx_transactions_txn_ts (txn_ts),
    INDEX idx_transactions_store_ts (store_id, txn_ts),
    INDEX idx_transactions_payment_type (payment_type),
    CONSTRAINT fk_transactions_store
        FOREIGN KEY (store_id) REFERENCES stores (store_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS transaction_line_items (
    transaction_id VARCHAR(32) NOT NULL,
    line_no        SMALLINT UNSIGNED NOT NULL,
    product_id     VARCHAR(16) NOT NULL,
    qty            DECIMAL(10, 3) NOT NULL,
    unit_price     DECIMAL(10, 2) NOT NULL,
    line_subtotal  DECIMAL(12, 2) NOT NULL,
    line_discount  DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    line_total     DECIMAL(12, 2) NOT NULL,
    PRIMARY KEY (transaction_id, line_no),
    INDEX idx_line_items_product_transaction (product_id, transaction_id),
    CONSTRAINT fk_line_items_transaction
        FOREIGN KEY (transaction_id) REFERENCES transactions (transaction_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_line_items_product
        FOREIGN KEY (product_id) REFERENCES products (product_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE = InnoDB;
