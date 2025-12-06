import os
from dataclasses import dataclass

@dataclass
class PayHandlerConfig:
    prefix: str = os.getenv('PAYMENT_HANDLER_PREFIX')

@dataclass
class PayWebhookConfig:
    prefix: str = os.getenv('PAYMENT_WEBHOOK_PREFIX')

@dataclass
class PaymentsConfig:

    host: str = os.getenv('PAYMENT_HOST')
    port: int = int(os.getenv('PAYMENT_PORT'))

    handler: PayHandlerConfig = None
    weebhook: PayWebhookConfig = None

    def __post_init__(self):
        if not self.handler: self.handler = PayHandlerConfig()
        if not self.weebhook: self.weebhook = PayWebhookConfig()

@dataclass
class Config:

    payments: "PaymentsConfig" = None

    def __post_init__(self):
        if not self.payments: self.payments = PaymentsConfig()


config = Config()