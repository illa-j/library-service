from django.contrib import admin

from library.models import Author, Book, Borrowing, Payment

admin.site.register(Author)
admin.site.register(Book)
admin.site.register(Borrowing)
admin.site.register(Payment)
