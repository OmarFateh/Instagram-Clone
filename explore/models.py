from django.db import models
from django.urls import reverse
            
from .utils import arabic_slugify


class HashtagManager(models.Manager):
    """
    Override the hashtag manager.
    """
    def created_or_new(self, title):
        """
        Take a title of a hashtag, and get it if it's already exist, and if not, create a new one. 
        """
        title = title.strip()
        # get queryset of all hashtags with that title.
        qs = self.get_queryset().filter(name__iexact=title)
        # if hashtags exist.
        if qs.exists():
            # get the first hashtag of the queryset.
            return qs.first(), False
        # if not, create new hashtag.   
        return Hashtag.objects.create(name=title), True

    def hashtag_to_qs(self, hashtags_str):
        """
        Take a string of hashtags, get rid of '#', split it using space as a delim, 
        and return a queryset of hashtags.  
        """
        hashtags_ids = []
        # take away any # in hashtags string and split it using space as a delim.
        # here, a space is used a delim, so it's not allowed in the hashtag name.
        hashtags_list = hashtags_str.replace("#", "").split()
        for hashtag in hashtags_list:
            # get or create each hashtag by using created_or_new method.
            obj, created = self.created_or_new(hashtag)
            # append each hashtag's id to a list of hashtags ids
            hashtags_ids.append(obj.id) 
        # get queryset of hashtags by filtering their ids.    
        qs = self.get_queryset().filter(id__in=hashtags_ids).distinct()
        return qs
    

class Hashtag(models.Model):
    """
    Hashtag model.
    """
    name = models.CharField(max_length=256, verbose_name='hashtag')
    slug = models.SlugField(unique=True, allow_unicode=True, null=True, blank=True)

    objects = HashtagManager()

    class Meta:
        verbose_name = 'Hashtag'
        verbose_name_plural = 'Hashtags'

    def __str__(self):
        # Return hashtag's title.
        return self.name   

    def save(self, *args, **kwargs):
        # Override the save method and slugify the hashtag name before saving. 
        if not self.slug:
            self.slug = arabic_slugify(self.name)
        super(Hashtag, self).save(*args, **kwargs)     

    def get_absolute_url(self):
        # Return absolute url of the hashtag by its slug.
        return reverse("explore:hashtag", kwargs={"hashtag_slug": self.slug})