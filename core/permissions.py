# core/permissions.py
from rest_framework import permissions

class IsAdminOrTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.groups.filter(name='Teachers').exists()

class IsAdminOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff

class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Students').exists()

class IsParent(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Parents').exists()