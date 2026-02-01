from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.serializers import (
    UserSerializer,
    TokenBlacklistSerializer
)


class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TokenBlacklistSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Successfully logged out."
            },
            status=status.HTTP_200_OK
        )


class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user
