from django.db import models
from core.models import Project

class Sentence(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    content = models.TextField()

    def __str__(self):
        return self.content
    
class Label(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#007bff")  # Store color codes
    
    # def __str__(self):
    #     return {"name": self.name, "color": self.color}

class Annotation(models.Model):
    sentence = models.ForeignKey(Sentence, on_delete=models.CASCADE)
    pre_label = models.ForeignKey(Label, related_name='pre_annotations', on_delete=models.CASCADE, null=True, blank=True)
    post_label = models.ForeignKey(Label, related_name='post_annotations', on_delete=models.CASCADE, null=True, blank=True)
    # text = models.CharField(max_length=255)
