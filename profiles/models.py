import os
from PIL import Image

from django.db import models
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.models import User

from notifications.models import Notification
from item.models import BaseTimestamp


def user_image(instance, filename):
    """
    Upload the user image into the path and return the uploaded image path.
    """
    return f'users/{instance.owner}/profile/{filename}'


class UserFollow(BaseTimestamp):
    """
    A model for followers many to many relations.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    profile = models.ForeignKey("UserProfile", on_delete=models.CASCADE)


class UserProfileQuerySet(models.QuerySet):
    """
    Override the user profile queryset.
    """
    def suggested_profiles(self, user):
        """
        Take a user object and return queryset of mutual profiles between the user and his following,
        and the profiles that are in user's followers but not in his following,
        orderd by the latest created ones.
        """
        user_profile = user
        # following
        followed_exist = user_profile.following.exists()
        followed_users_id = []
        if followed_exist:
            followed_users_id = user_profile.following.values_list("userprofile__id", flat=True)  
        # followers
        followers_exist = user_profile.user.followers.exists()
        followers_users_id = []
        if followers_exist:
            followers_users_id = user_profile.user.followers.values_list("user__id", flat=True) 
        # followers but not following
        followers_not_followed_users_id = set(followers_users_id).difference(set(followed_users_id))
        # mutual friends,  user following --> their following who are not in user following
        mutual_friends_users_id = []
        for obj in user_profile.following.all():
            for x in obj.userprofile.following.values_list("userprofile__id", flat=True):
                if x not in followed_users_id and x != user_profile.id:
                    mutual_friends_users_id.append(x)
        # pending_requests, private profiles which haven't accepted the follow request yet
        pending_exist = user_profile.noti_from_user.filter(status='sent').exists()
        pending_requests_users_id = [] 
        if pending_exist:
            pending_requests_users_id = user_profile.noti_from_user.filter(status='sent').values_list("receiver__id", flat=True)             
        # suggestions
        suggested_friends_users_id = list((set(mutual_friends_users_id) | followers_not_followed_users_id).symmetric_difference(set(pending_requests_users_id)))
        return self.filter(user__id__in=suggested_friends_users_id).order_by('-created_at')    


class UserProfileManager(models.Manager):
    """
    Override the user profile manager.
    """
    def get_queryset(self, *args, **kwargs):
        """
        Get the user profile queryset.
        """
        return UserProfileQuerySet(self.model, using=self._db)

    def all(self):
        """
        Override the all method and return queryset excluded from the user itself.
        """
        qs = self.get_queryset().all()
        try:
            if self.instance:
                qs = qs.exclude(user=self.instance)
        except:
            pass
        return qs

    def is_request_sent(self, sender, receiver):
        """
        Take a sender and a receiver and check if a follow request has been already sent by a sender to a receiver.  
        """
        return Notification.objects.filter(sender=sender, 
                receiver=receiver, status='sent', notification_type='follow_request').exists()            

    def get_profile(self, username):
        """
        Take a username of a user and get his profile. 
        """
        username = username.strip()
        # get queryset of profiles with this username.
        qs = self.get_queryset().filter(user__username__iexact=username)
        if qs.exists():
            return qs.first()
        return False

    def tag_to_qs(self, tags_str):
        """
        Take a string of usernames (tags), get rid of '@', split it using space as a delim, 
        and return a queryset of profiles of these usernames.  
        """
        tags_ids = []
        # take away any @ in tags string and split it using space as a delim.
        # here, a space is used a delim, so it's not allowed in the tag name.
        tags_list = tags_str.replace("@", "").split()
        for tag in tags_list:
            # get profile of each tag by using get_profile method. 
            obj = self.get_profile(tag)
            if obj:
                # append each tag's id to a list of tags ids.
                tags_ids.append(obj.id)  
        # get queryset of profiles of these tags by filtering their ids.    
        qs = self.get_queryset().filter(id__in=tags_ids).distinct()
        return qs

    def suggested_profiles(self, user):
        """
        Add suggested profiles method to the user profile manager.
        Take a user and return his suggested profiles.
        """
        return self.get_queryset().suggested_profiles(user)

    def get_profiles_list_data(self, q):
        """
        Take q, which is the entered value in search input field.
        Get list of profiles' data which their usernames start with q.
        """
        profiles_qs = self.get_queryset().filter(user__username__startswith=q).order_by('user__username')
        profiles_list_data = []
        if profiles_qs.exists():
            for profile in profiles_qs:
                if profile.photo:
                    profiles_data = {
                        'id':profile.user.id, 
                        'username':profile.user.username, 
                        'photo':profile.photo.url,
                        'profile_url':profile.get_absolute_url,
                    }
                else:
                    profiles_data = {
                        'id':profile.user.id, 
                        'username':profile.user.username,
                        'profile_url':profile.get_absolute_url,
                    }                        
                profiles_list_data.append(profiles_data)
        return profiles_list_data     
    

class UserProfile(BaseTimestamp):
    """
    User profile model.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    following = models.ManyToManyField(User, related_name='followers', blank=True, through=UserFollow)
    photo = models.ImageField(upload_to=user_image)
    bio = models.CharField(max_length=255, blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    website = models.URLField(blank=True, null=True) 
    private_account = models.BooleanField(default=False)   
    
    objects = UserProfileManager()

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'

    def __str__ (self):
        # Return user username.
        return self.user.username          

    # def save(self, *args, **kwargs):
    #     # Override the save method and resize the profile photo 250 x 250 ,before saving. 
    #     super(UserProfile, self).save(*args, **kwargs) 
    #     SIZE = 250, 250
    #     if self.photo:
    #         pic = Image.open(self.photo.name)
    #         pic.thumbnail(SIZE, Image.LANCZOS)
    #         pic.save(self.photo.name)    

    @property
    def get_absolute_url(self):
        # Return absolute url of the user profile detail by his username.
        return reverse("profiles:detail", kwargs={"username": self.user.username})

    @property
    def get_edit_absolute_url(self):
        # Return edit profile absolute url of the user profile by his username.
        return reverse("profiles:update", kwargs={"username": self.user.username})  

    def get_followers_absolute_url(self):
        # Return profile followers absolute url of the user profile by his username.
        return reverse("profiles:followers", kwargs={"username": self.user.username})

    def get_following_absolute_url(self):
        # Return profile following absolute url of the user profile by his username.
        return reverse("profiles:following", kwargs={"username": self.user.username})    

    def get_api_follow_url(self):
        # Return api url of the user follow toggle by his username
        return reverse('profiles:follow-api-toggle', kwargs={"username": self.user.username})      
    
    @property
    def get_follower(self):
        # Return the user's followers excluded from the user himself.
        users = self.user.followers.all()
        return users.exclude(user__username=self.user.username)

    @property
    def owner(self):
        # Return user.
        return self.user    


# profile_obj = UserProfile.objects.first()
# profile_obj.following.all()  ---> people who follow this profile
# user.followers.all()        ---> people who is being followed by this user 