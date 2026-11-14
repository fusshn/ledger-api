"""請求內容的檢查與轉型。

檢查失敗時拋 ValidationError，由 app.py 的錯誤處理統一回應
（預設 400；參照的資料不存在或不相符時用 422），
data 裡列出每個欄位的錯誤原因。
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import request

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(Exception):
    def __init__(self, errors, message="輸入資料有誤", status=400):
        super().__init__(message)
        self.message = message
        self.errors = errors  # {欄位: 原因}
        self.status = status


def get_json_object():
    """取得 JSON 物件本體。不是 JSON 物件時拋 ValidationError。"""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValidationError({"body": "請送出 JSON 物件"}, "請求內容必須是 JSON 物件")
    return body


class Parser:
    """逐欄檢查，把錯誤收集起來一次回報。"""

    def __init__(self, body):
        self.body = body
        self.errors = {}
        self.values = {}

    def has(self, field):
        return field in self.body

    def _get(self, field, required, nullable=False):
        """回傳 (原始值, 是否需要繼續檢查)。

        沒送：必填時記錯誤。送 null：nullable 時記成 None（用來清空欄位），
        否則記錯誤。
        """
        if field not in self.body:
            if required:
                self.errors[field] = "必填"
            return None, False
        raw = self.body[field]
        if raw is None:
            if nullable:
                self.values[field] = None
            else:
                self.errors[field] = "必填" if required else "不可以是 null"
            return None, False
        return raw, True

    def text(self, field, *, required=False, nullable=False):
        """nullable 的欄位送空字串時存成 None；其他欄位不接受空字串。"""
        raw, present = self._get(field, required, nullable)
        if not present:
            return None
        if not isinstance(raw, str):
            return self._error(field, "必須是字串")
        value = raw.strip()
        if not value:
            if nullable:
                return self._set(field, None)
            return self._error(field, "不可以是空字串")
        return self._set(field, value)

    def choice(self, field, choices, *, required=False):
        raw, present = self._get(field, required)
        if not present:
            return None
        if raw not in choices:
            return self._error(field, "只能是 " + "、".join(choices) + " 之一")
        return self._set(field, raw)

    def currency(self, field, *, required=False):
        raw, present = self._get(field, required)
        if not present:
            return None
        if not isinstance(raw, str) or not _CURRENCY_RE.match(raw.strip().upper()):
            return self._error(field, "必須是三碼英文幣別，例如 TWD")
        return self._set(field, raw.strip().upper())

    def decimal(
        self, field, *, required=False, int_digits, scale, positive=False
    ):
        """對應 numeric(int_digits + scale, scale)。"""
        raw, present = self._get(field, required)
        if not present:
            return None
        # bool 是 int 的子類別，要先排除。
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            return self._error(field, "必須是數字或數字字串")
        try:
            value = Decimal(str(raw).strip())
        except InvalidOperation:
            return self._error(field, "必須是數字或數字字串")
        if not value.is_finite():
            return self._error(field, "必須是有限的數字")
        if positive and value <= 0:
            return self._error(field, "必須大於 0")
        if -value.as_tuple().exponent > scale:
            return self._error(field, f"小數最多 {scale} 位")
        if abs(value) >= Decimal(10) ** int_digits:
            return self._error(field, f"整數部分最多 {int_digits} 位")
        return self._set(field, value)

    def integer(
        self, field, *, required=False, nullable=False, min_value=None, max_value=None
    ):
        raw, present = self._get(field, required, nullable)
        if not present:
            return None
        if isinstance(raw, bool) or not isinstance(raw, int):
            return self._error(field, "必須是整數")
        if (min_value is not None and raw < min_value) or (
            max_value is not None and raw > max_value
        ):
            return self._error(field, f"必須介於 {min_value} 到 {max_value}")
        return self._set(field, raw)

    def date(self, field, *, required=False):
        raw, present = self._get(field, required)
        if not present:
            return None
        if not isinstance(raw, str) or not _DATE_RE.match(raw):
            return self._error(field, "必須是 YYYY-MM-DD 格式的日期")
        try:
            value = date.fromisoformat(raw)
        except ValueError:
            return self._error(field, "不是有效的日期")
        return self._set(field, value)

    def reject(self, fields, reason):
        for field in fields:
            if field in self.body:
                self.errors[field] = reason

    def finish(self):
        if self.errors:
            raise ValidationError(self.errors)
        return self.values

    def _set(self, field, value):
        self.values[field] = value
        return value

    def _error(self, field, reason):
        self.errors[field] = reason
        return None
