# JApi

Django application for providing JSON API, based on the Django admin interface.


### Requirements

* Django ( http://djangoproject.com/ )(Required)


### Installation

1- Download the application

2- Add the package "japi" to your path.

3- Add the app "japi" into your settings.py:

    INSTALLED_APPS = (
        ...
        'japi',
    )


4- Add the middleware authentication in settings.py:

    MIDDLEWARE_CLASSES = (
    	...
    	'japi.middleware.ApiAuth',
    )


5- Add the urls of the app "japi" into your urls.py:

    import japi
    japi.autodiscover()
    urlpatterns = patterns('',
    	...
    	(r'^api/', include(japi.site.urls)),
    )



### Configuration

1- Create a file api.py into the you app, and register you model in the JApi::

    import japi
    from japi.options import ModelApi
    from models import Model1, Model2
    
    class Model1ModelApi(ModelApi):
    	fields = ('name', )
    	exclude = ()
    	order_by = ()
    	list_per_page = 100
    
    japi.site.register(Model1, Model1ModelApi)
    japi.site.register(Model2)


2- I can override, in ModelApi?

2.1- Atributes:

    fields = None
    exclude = []
    form = forms.ModelForm
    order_by = []
    list_per_page = 100


2.2- Methods:

    def formfield_for_choice_field(self, db_field, request=None, **kwargs):
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
    def queryset(self, request):
    def save_form(self, request, form, change):
    def save_model(self, request, obj, form, change):
    def delete_model(self, request, obj):
    def changelist_view(self, request, extra_context=None):
    def class_view(self, request, extra_context=None):
    def add_view(self, request, extra_context=None):
    def change_view(self, request, object_id, extra_context=None):
    def delete_view(self, request, object_id, extra_context=None):



### Usage

1- For you autenticate, send username and password variable using GET or POST message to:

    /api/auth/
    
    This is return a JSON, containing the token variable. You use the token variable into GET of all requests.


2- Get class JSON. You can see a class atributes. Use a GET request to:
	
    /api/APP_NAME/MODEL_NAME/class/
    
    Ex.: http://127.0.0.1:8000/api/my_app/model1/class/?token=7sThjpKyXdqOFC5rHzrD2TQSpH1f3P


3- Get the list JSON. Use a GET request to:

    /api/APP_NAME/MODEL_NAME/
    
    Ex.: http://127.0.0.1:8000/api/my_app/model1/?token=7sThjpKyXdqOFC5rHzrD2TQSpH1f3P


3.1- You can make some queries, passing them GET.

    Ex.: http://127.0.0.1:8000/api/my_app/model1/?token=7sThjpKyXdqOFC5rHzrD2TQSpH1f3P&name=Leonardo


3.2- You can also set the number of paging models (list_per_page), order(order_by), the page(page) or fields(fields)


4- Add model. You send a POST request containing all atributes to:

    /api/APP_NAME/MODEL_NAME/add/


5- Edit model. You send a POST request containing the attributes you can change to:

    /api/APP_NAME/MODEL_NAME/OBJECT_ID/


6- Delete model. You send a GET request to:

    /api/VERSION_API/APP_NAME/MODEL_NAME/OBJECT_ID/delete/


7- JSON doc. You send a GET request to:

    /api/
