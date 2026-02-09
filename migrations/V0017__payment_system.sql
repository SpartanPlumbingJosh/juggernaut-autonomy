-- Create payment methods table
CREATE TABLE payment_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    provider VARCHAR(32) NOT NULL,  -- stripe, paypal, etc
    method_id VARCHAR(128) NOT NULL, -- payment method ID from provider
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE UNIQUE INDEX idx_payment_methods_user_provider ON payment_methods(user_id, provider, method_id);

-- Expand revenue_events for payment tracking
ALTER TABLE revenue_events ADD COLUMN payment_method_id UUID REFERENCES payment_methods(id);
ALTER TABLE revenue_events ADD COLUMN payment_intent_id VARCHAR(128);

-- User product access
CREATE TABLE user_products (
    user_id UUID NOT NULL,
    product_id UUID NOT NULL,
    access_granted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (user_id, product_id)
);
