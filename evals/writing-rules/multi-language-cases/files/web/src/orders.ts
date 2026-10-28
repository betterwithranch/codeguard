export const ORDER_STATUSES = ["open", "paid", "shipped"] as const;

export type OrderStatus = (typeof ORDER_STATUSES)[number];
