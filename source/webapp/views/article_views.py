from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import urlencode
from django.views.generic import ListView, DetailView, CreateView, \
    UpdateView, DeleteView, FormView
from webapp.forms import ArticleForm, ArticleCommentForm, SimpleSearchForm, FullSearchForm
from webapp.models import Article, Tag
from django.core.paginator import Paginator


class IndexView(ListView):
    context_object_name = 'articles'
    model = Article
    template_name = 'article/index.html'
    ordering = ['-created_at']
    paginate_by = 5
    paginate_orphans = 1

    def get(self, request, *args, **kwargs):
        self.form = self.get_search_form()
        self.search_query = self.get_search_query()
        self.tag_query = self.get_tag_query()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        if self.search_query:
            context['query'] = urlencode({'search': self.search_query})
        context['form'] = self.form
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.search_query:
            queryset = queryset.filter(
                Q(title__icontains=self.search_query)
                | Q(author__icontains=self.search_query)
                | Q(tags__name__iexact=self.search_query)
            )
        if self.tag_query:
            queryset = queryset.filter(
                Q(tags__name__iexact=Tag.objects.get(pk=self.tag_query))
            )
        return queryset

    def get_search_form(self):
        return SimpleSearchForm(self.request.GET)

    def get_search_query(self):
        if self.form.is_valid():
            return self.form.cleaned_data['search']
        return None

    def get_tag_query(self):
        if self.form.is_valid():
            return self.request.GET.get('tag')
        return None


class ArticleView(DetailView):
    template_name = 'article/article.html'
    model = Article
    context_object_name = 'article'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ArticleCommentForm()
        comments = context['article'].comments.order_by('-created_at')
        self.paginate_comments_to_context(comments, context)
        return context

    def paginate_comments_to_context(self, comments, context):
        paginator = Paginator(comments, 3, 0)
        page_number = self.request.GET.get('page', 1)
        page = paginator.get_page(page_number)
        context['paginator'] = paginator
        context['page_obj'] = page
        context['comments'] = page.object_list
        context['is_paginated'] = page.has_other_pages()


class ArticleCreateView(CreateView):
    model = Article
    template_name = 'article/create.html'
    form_class = ArticleForm

    def form_valid(self, form):
        self.object = form.save()
        tags = self.request.POST.get('tags')
        tags = tags.split(',')
        for tag in tags:
            tag, _ = Tag.objects.get_or_create(name=tag.strip())
            self.object.tags.add(tag)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('article_view', kwargs={'pk': self.object.pk})


class ArticleUpdateView(UpdateView):
    model = Article
    template_name = 'article/update.html'
    form_class = ArticleForm
    context_object_name = 'article'

    def get(self, request, *args, **kwargs):
        article = get_object_or_404(Article, pk=self.kwargs['pk'])
        form = self.form_class(instance=article)
        tags = article.tags.all().values('name')
        str_tag = ''
        for tag in tags:
            str_tag += tag['name'] + ', '
        form.fields['tags'].initial = str_tag.strip(', ')
        return render(request, self.template_name, context={'form': form, 'article': article})

    def form_valid(self, form):
        article = get_object_or_404(Article, pk=self.kwargs['pk'])
        article.tags.clear()
        self.object = form.save()
        tags = self.request.POST.get('tags')
        tags = tags.split(',')
        for tag in tags:
            tag, _ = Tag.objects.get_or_create(name=tag.strip())
            self.object.tags.add(tag)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('article_view', kwargs={'pk': self.object.pk})


class ArticleDeleteView(DeleteView):
    model = Article
    template_name = 'article/delete.html'
    context_object_name = 'article'
    success_url = reverse_lazy('index')


class ArticleSearchView(FormView):
    template_name = 'article/search.html'
    form_class = FullSearchForm

    def form_valid(self, form):
        text = form.cleaned_data.get('text')
        author = form.cleaned_data.get('author')
        query = Q()
        if text:
            query = query & self.get_text_query(form, text)
        if author:
            query = query & self.get_author_query(form, author)
        articles = Article.objects.filter(query).distinct()
        context = self.get_context_data()
        context['articles'] = articles
        return self.render_to_response(context)

    def get_text_query(self, form, text):
        query = Q()
        in_title = form.cleaned_data.get('in_title')
        if in_title:
            query = query | Q(title__icontains=text)
        in_text = form.cleaned_data.get('in_text')
        if in_text:
            query = query | Q(text__icontains=text)
        in_tags = form.cleaned_data.get('in_tags')
        if in_tags:
            query = query | Q(tags__name__iexact=text)
        in_comment_text = form.cleaned_data.get('in_comment_text')
        if in_comment_text:
            query = query | Q(comments__text__icontains=text)
        return query

    def get_author_query(self, form, author_name):
        query = Q()
        article_author = form.cleaned_data['article_author']
        if article_author:
            query = query | Q(author__iexact=author_name)
        article_comment_author = form.cleaned_data['comment_author']
        if article_comment_author:
            query = query | Q(comments__author__iexact=author_name)
        return query
