from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wrap DRF + Django exceptions into a consistent response format.

    Success responses (2xx) are not touched.
    Only errors come through here.
    """
    response = drf_exception_handler(exc, context)

    # If DRF handled it, wrap it
    if response is not None:
        return Response(
            {
                "success": False,
                "status_code": response.status_code,
                "errors": response.data,
            },
            status=response.status_code,
        )

    # Unhandled exceptions -> 500
    logger.exception("Unhandled API exception", exc_info=exc)

    return Response(
        {
            "success": False,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "errors": {"detail": "Internal server error."},
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
