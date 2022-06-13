# -*- coding: utf-8 -*-
from system.env import env


# CHANNELS
# ------------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env.str("REDIS_URL", default="redis://localhost:6379/0")],
        },
    },
}
