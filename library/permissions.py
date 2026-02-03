from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff


class IsBorrowerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return False

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if request.method in permissions.SAFE_METHODS:
            return obj.user == request.user
        return False