from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from library.models import (
    Author,
    Book
)
from library.permissions import (
    IsAdminOrReadOnly,
)
from library.serializers import (
    AuthorSerializer,
    AuthorPhotoSerializer,
    BookSerializer,
    BookCoverImageSerializer,
)


class AuthorViewSet(ModelViewSet):
    serializer_class = AuthorSerializer
    queryset = Author.objects.all()
    permission_classes = (IsAuthenticated, IsAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action == "upload_photo":
            return AuthorPhotoSerializer
        return AuthorSerializer

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-photo",
    )
    def upload_photo(self, request, pk=None):
        author = self.get_object()
        serializer = self.get_serializer(author, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookViewSet(ModelViewSet):
    serializer_class = BookSerializer
    queryset = Book.objects.all()
    permission_classes = (IsAuthenticated, IsAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action == "upload_cover_image":
            return BookCoverImageSerializer
        return BookSerializer

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-cover-image",
    )
    def upload_cover_image(self, request, pk=None):
        author = self.get_object()
        serializer = self.get_serializer(author, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
