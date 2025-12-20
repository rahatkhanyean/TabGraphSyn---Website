from __future__ import annotations

import secrets

from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.permissions_policy = getattr(settings, 'PERMISSIONS_POLICY', None)
        self.cross_origin_resource_policy = getattr(settings, 'CROSS_ORIGIN_RESOURCE_POLICY', None)
        self.csp_enabled = getattr(settings, 'CSP_ENABLED', False)
        self.csp_report_only = getattr(settings, 'CSP_REPORT_ONLY', False)

    def __call__(self, request):
        if self.csp_enabled:
            request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        if self.permissions_policy and 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = self.permissions_policy
        if self.cross_origin_resource_policy and 'Cross-Origin-Resource-Policy' not in response:
            response['Cross-Origin-Resource-Policy'] = self.cross_origin_resource_policy
        if self.csp_enabled:
            nonce = getattr(request, 'csp_nonce', '')
            policy = self._build_csp(nonce)
            header = 'Content-Security-Policy-Report-Only' if self.csp_report_only else 'Content-Security-Policy'
            if policy and header not in response:
                response[header] = policy
        return response

    def _normalize(self, value):
        if not value:
            return []
        if isinstance(value, str):
            return value.split()
        return list(value)

    def _build_csp(self, nonce: str) -> str:
        script_src = self._normalize(getattr(settings, 'CSP_SCRIPT_SRC', ["'self'"]))
        if nonce:
            script_src = script_src + [f"'nonce-{nonce}'"]
        directives = {
            'default-src': self._normalize(getattr(settings, 'CSP_DEFAULT_SRC', ["'self'"])),
            'script-src': script_src,
            'style-src': self._normalize(getattr(settings, 'CSP_STYLE_SRC', ["'self'"])),
            'img-src': self._normalize(getattr(settings, 'CSP_IMG_SRC', ["'self'"])),
            'font-src': self._normalize(getattr(settings, 'CSP_FONT_SRC', ["'self'"])),
            'connect-src': self._normalize(getattr(settings, 'CSP_CONNECT_SRC', ["'self'"])),
            'base-uri': self._normalize(getattr(settings, 'CSP_BASE_URI', ["'self'"])),
            'form-action': self._normalize(getattr(settings, 'CSP_FORM_ACTION', ["'self'"])),
            'frame-ancestors': self._normalize(getattr(settings, 'CSP_FRAME_ANCESTORS', ["'none'"])),
        }
        parts = []
        for key, values in directives.items():
            if values:
                parts.append(f"{key} {' '.join(values)}")
        return '; '.join(parts)
