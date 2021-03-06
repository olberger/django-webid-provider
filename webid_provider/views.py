#!/usr/bin/python
# vim: set expandtab tabstop=4 shiftwidth=4:
# -*- coding: utf-8 -*-
 
#
# Copyright (C) 2011 bennomadic at gmail dot com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
"""
    views
    ~~~~~~~~
 
    :authors:       Ben Carrillo, Julia Anaya
    :organization:  rhizomatik labs
    :copyright:     Cooperative Quinode
    :license:       GNU GPL version 3 or any later version
                    (details at http://www.gnu.org)
    :contact:       bennomadic at gmail dot com
    :dependencies:  python (>= version 2.6)
    :change log:
    :TODO:
"""
import hashlib
import json
import logging
# import os
import random
# import re
# #from datetime import datetime
# 
from django import template
from django.contrib.auth import logout
# from django.core.exceptions import ImproperlyConfigured
# from django.db import IntegrityError
from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.template import RequestContext
# #from django.utils.translation import ugettext_lazy as _
# #from django.views.decorators.csrf import csrf_protect
#from django.views.generic import list_detail
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.core.urlresolvers import reverse

from django.conf import settings
# from django.db import models
# 
# #XXX this import should be handled on certs.utils now
# from OpenSSL import crypto
# 
# #XXX FIXME fix relative imports
# #from .models import PubKey,
from .models import WebIDUser, CertConfig, Cert
# #from .certs.utils import create_cert # deprecated
from .certs.utils import CertCreator
# 
# #XXX PKCS12 SHIT
# #... that we could shut down by the moment...
# from .certs.utils import gen_httpwebid_selfsigned_cert_pemfile,\
#         pemfile_2_pkcs12file
# from .forms import WebIdIdentityForm
# 
from django.contrib.auth import login as auth_login  # authenticate
from django.contrib.auth.forms import UserCreationForm
# from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
# 
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# 
logger = logging.getLogger(name=__name__)
# 
#############################################################
# VIEWS BEGIN
#############################################################

class LoginRequiredMixin(object):
    """ A mixin requiring a user to be logged in. """
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(*args, **kwargs)

################
# CREATE USER
################
#XXX we should hook django register app here, instead of this
 
 
def create_user(request):
    """
    creates user and redirects to the page
    for installing a cert.
    """
    #XXX should check it's anon_login,
    #or redirect to logout in other case.
 
    #This view SHOULD NOT be available if this config
    #is not allowed in settings. We can do that by
    #manually removing from urls.
    #We could also put here a decorator that checks
    #the settings and allows/denies access to view.
 
    #XXX TODO
    #on this view (or another different??) we should
    #introduce an **email verification** step.
 
    errors = False
    messages = []
 
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            if not errors:
                u = form.save()
 
                if settings.DEBUG:
                    logger.debug('created user... %s' % u)
                    logger.debug('active? %s' % u.is_active)
 
                u.backend = 'django.contrib.auth.backends.ModelBackend'
                auth_login(request, u)
 
                return redirect('webidprovider-add_cert')
 
            return render_to_response(
                'django_webid/provider/create_user.html', {
                'form': form,
                "MEDIA_URL": settings.MEDIA_URL,
                "STATIC_URL": settings.STATIC_URL,
                'messages': messages,
                },
                context_instance=RequestContext(request))
    else:
        form = UserCreationForm()
 
    return render_to_response('webid_provider/create_user.html',
     {
        'form': form,
        "MEDIA_URL": settings.MEDIA_URL,
        "STATIC_URL": settings.STATIC_URL,
        'messages': messages,
     }, context_instance=RequestContext(request))
 
 
####################
# Log out
###################
 
def logout_view(request):
    logout(request)
    return redirect('/')

###########################################
# CERTS VIEWS                             #
###########################################
 
#####################
# CERT:LIST
#####################

class CertListView(LoginRequiredMixin, ListView):
    template_name = 'webid_provider/cert_list.html'
    #XXX not working with template object name??
    #template_object_name = "certs",
    #paginate_by = 25
    #context_object_name = 'posts'

    def get_queryset(self):
        return Cert.objects.filter(pubkey__user=self.request.user).\
                order_by('-pubkey__created')

#####################
# CERT:DETAIL
#####################
 
class CertDetailView(LoginRequiredMixin, DetailView):
    #template_name = 'webid_provider/cert_detail.html'
    #model = Cert
    
    def get_object(self):

        # Look up the Cert (and raise a 404 if not found)
        cert = get_object_or_404(Cert, pk=self.kwargs['cert_id'])
        if cert.pubkey.user != self.request.user:
            raise Http404

        # Return the object
        return cert

 
#####################
# CERT:REVOKE
#####################
 
 
def revoke_cert(cert):
    cert.pubkey.is_active = False
    cert.pubkey.save()
 
class RevokeCertConfirmView(CertDetailView):
    template_name = "webid_provider/cert_revoke.html"
 
@login_required
def cert_revoke(request, cert_id):
    # Look up the Cert (and raise a 404 if not found)
    cert = get_object_or_404(Cert, pk=cert_id)
    if cert.pubkey.user != request.user:
        raise Http404
 
    if request.method == "POST":
        hidden = request.POST.get('post', None)
        if hidden and hidden == "yes":
            revoke_cert(cert)
            #XXX we should use messages here.
            return render_to_response(
                'webid_provider/cert_revoked.html',
                {
                    "MEDIA_URL": settings.MEDIA_URL,
                    "STATIC_URL": settings.STATIC_URL,
                })
    if request.method == "GET":
        # Show the detail page
        # with a confirmation message.
        detail_view = RevokeCertConfirmView.as_view()
#         return list_detail.object_detail(
#             request,
#             queryset=Cert.objects.all(),
#             object_id=cert_id,
#             template_name="webid_provider/cert_revoke.html"
#         )
        return detail_view(
                           request,
                           cert_id=cert_id
                           )

 
#####################
# CERT:ADD
#####################
 
 
@login_required
#XXX doubt... will this decorator work also for webid-auth?
# not logged in, it should check if anon register is allowed
#and redirect there...
#XXX but now it's redirecting to the accounts url that is not
#being loaded...
def add_cert_to_user(request):
    messages = []
    if request.method == 'POST':
        if 'pubkey' in request.POST:
            user = request.user
            spkac_str = str(request.POST['pubkey'])
 
            return_iframe = request.REQUEST.get('iframe', None)
            if return_iframe and return_iframe == "true":
                do_iframe = True
            else:
                do_iframe = False
 
            return_multipart = request.REQUEST.get('multipart', None)
            if return_multipart and return_multipart == "true":
                do_multipart = True
            else:
                do_multipart = False
 
            skip_issuer_signing = request.REQUEST.get('skipsign', False)
            if skip_issuer_signing and skip_issuer_signing == "true":
                skip_sign = True
            else:
                skip_sign = False
 
            #XXX should catch exceptions here (bad pubkey???)
            #XXX or tampered challenge :)
 
            kwargs = {}
            kwargs['user_agent_string'] = request.META['HTTP_USER_AGENT']
            kwargs['skip_sign'] = skip_sign
            #XXX TODO get kwargs from the post advanced fields
            c = CertCreator(spkac_str, user, **kwargs)
            c.create_cert()
 
            if do_iframe:
                # We create an iframe with b64encoded cert as src.
                # works on FF, opera. Not working in chrome
                #http://code.google.com/p/chromium/issues/detail?id=114142
                #Iframe use like this:
                #http://blog.magicaltux.net/2009/02/09/
                #using-ssl-keys-for-client-authentification/
                #XXX what about MSIE??
 
                certdump = c.get_b64_cert_dump()
                sha1fingerprint = c.get_sha1_fingerprint()
 
                return render_to_response(
                        'webid_provider/webid_b64_cert.html',
                        {
                            "MEDIA_URL": settings.MEDIA_URL,
                            "STATIC_URL": settings.STATIC_URL,
                            "b64cert": certdump,
                            "sha1fingerprint": sha1fingerprint,
                            "user": request.user,
                            }, context_instance=RequestContext(request))
 
            elif do_multipart:
                # As a workaround for iframes, experimenting with multipart
                # black magic
                # XXX Here Be Dragons
                # chrome also misbehaves with this :(
                #http://code.google.com/p/chromium/issues/detail?id=114140
                certdump = c.get_cert_dump()
                sha1fingerprint = c.get_sha1_fingerprint()
                t = template.loader.get_template(
                        'webid_provider/webid_cert_postinst.html')
                c = template.Context({
                            "MEDIA_URL": settings.MEDIA_URL,
                            "STATIC_URL": settings.STATIC_URL,
                            "sha1fingerprint": sha1fingerprint,
                            "user": request.user,
                            })
                rendered = t.render(c)
                BOUND = "BOUND"
                r = HttpResponse(
                        mimetype="multipart/x-mixed-replace;boundary=%s" % \
                                BOUND)
 
                N = "\r\n"
                NN = "\r\n\n"
 
                r.write("--" + BOUND + N +
                        'Content-Type: application/x-x509-user-cert' + NN)
                r.write(certdump)
                r.write(N + "--" + BOUND + N + 'Content-Type: text/html' + NN)
                r.write(rendered)
                r.write(N + "--" + BOUND + "--")
                return r
 
            else:
                # We deliver the cert as the only response
                certdump = c.get_cert_dump()
                r = HttpResponse(mimetype="application/x-x509-user-cert")
                r.write(certdump)
                session = request.session
                session['certdelivered'] = True
                sha1 = c.get_sha1_fingerprint()
                session['sha1fingerprint'] = sha1
                cert = Cert.objects.get(fingerprint_sha1=sha1)
                session['cert_id'] = cert.id
                return r
 
    app_conf = CertConfig.objects.single()
    r = random.getrandbits(100)
    challenge = hashlib.sha1(str(r)).hexdigest()
 
    user = request.user
    webiduser = WebIDUser.get_for_user(user)
    numpubkeys = webiduser.pubkey_set.count()
 
    return render_to_response('webid_provider/webid_add_to_user.html',
        {
        "HIDE_KEYGEN_FORM": app_conf.hide_keygen_form,
        "MEDIA_URL": settings.MEDIA_URL,
        #"ADMIN_MEDIA_PREFIX": settings.ADMIN_MEDIA_PREFIX,
        "STATIC_URL": settings.STATIC_URL,
        "challenge": challenge,
        'messages': messages,
        'user': request.user,
        'webiduser': webiduser,
        'numpubkeys': numpubkeys},
        context_instance=RequestContext(request))
 
 
def check_cert_was_delivered(request):
    """
    ajax view that returns certdelivered value from session
    or False if key is not found.
    """
    #XXX is there a decorator for this?
    if request.is_ajax():
        dlvrd = request.session.get('certdelivered', False)
        return HttpResponse(
                json.dumps({'certdelivered': dlvrd}),
                "application/javascript")
    else:
        return HttpResponse(status=400)
 
 
def cert_nameit(request):
    """
    ajax view that puts a comment on a new cert.
    """
    if request.is_ajax() and request.method == "POST":
        comment = request.POST.get('certname', None)
        cert_id = request.session.get('cert_id', None)
        res = False
        if cert_id and comment:
            cert_inst = Cert.objects.get(id=cert_id)
            if cert_inst:
                cert_inst.comment = comment
                cert_inst.save()
                res = True
        return HttpResponse(
                json.dumps({'named': res,
                    'id': cert_id,
                    'comment': comment}),
                "application/javascript")
    else:
        return HttpResponse(status=400)
 
 
def cert_post_inst(request):
    return render_to_response(
            'webid_provider/webid_cert_postinst.html',
            {
                "MEDIA_URL": settings.MEDIA_URL,
                "STATIC_URL": settings.STATIC_URL,
                "sha1fingerprint": request.session.get(
                    'sha1fingerprint', None),
                "user": request.user,
                }, context_instance=RequestContext(request))


# ###########################################
# # WEBID VIEWS                             #
# ###########################################
# # Deprecated by the content-negotiated view
# # in webidprofile
# 
# def render_webid(request, username=None):
#     uu = get_object_or_404(WebIDUser,
#             username=username)
#     return render_to_response('webid_provider/foaf/webid_rdfa.html',
#              {
#              "webiduser": uu,
#              "MEDIA_URL": settings.MEDIA_URL,
#              "STATIC_URL": settings.STATIC_URL,
#              })
#              #, context_instance=RequestContext(request))
# 
# 
# ###################################################
# ###########################################
# # OLD VIEWS THAT WE CAN KEEP BUT NEED TO BE
# # REFACTORED TO USE NEW FUNCTIONS
# ###########################################
# ###################################################
# 
# 
# def webid_identity_keygen(request):
#     """
#     Create only http-WebID certificate
#     using keygen in the browser
#     """
#     #XXX FIXME
#     # REFACTOR using above functions... :/
#     #XXX TODO:
#     #Detect if using IExplorer (support needed?)
#     #and leave the .p12 as a fallback mechanism.
#     #they say it's a good fallback for things like iphone
#     #sending the pkcs12 (w/ pass) by email.
# 
#     #XXX TODO: try also javascript CSR creation... which
#     #format does it produce??
# 
#     errors = False
#     messages = []
# 
#     if request.method == 'POST':
#         form = WebIdIdentityForm(request.POST)
#         if form.is_valid():
#             if not errors:
#                 webid = str(form.cleaned_data['webid'])
#                 nick = str(form.cleaned_data['nick'])
# 
#                 #XXX REFACTOR ##############################
#                 pubkey = re.sub('\s', '', str(request.POST['pubkey']))
#                 if settings.DEBUG:
#                     logger.debug('PUBKEY=%s' % pubkey)
#                     #print('PUBKEY=%s' % pubkey)
#                 spki = crypto.NetscapeSPKI(pubkey)
#                 cert = crypto.X509()
#                 cert.get_subject().C = "US"
#                 cert.get_subject().ST = "Minnesota"
#                 cert.get_subject().L = "Minnetonka"
#                 cert.get_subject().O = "my company"
#                 cert.get_subject().OU = "WebID"
#                 cert.get_subject().CN = nick
#                 cert.set_serial_number(001)
#                 cert.gmtime_adj_notBefore(0)
#                 cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
#                 cert.set_issuer(cert.get_subject())
#                 URI_STR = 'URI:%s' % (webid)
#                 ext = crypto.X509Extension('subjectAltName', 1,
#                     URI_STR)
#                 cert.add_extensions([ext])
#                 cert.set_version(2)  # version 3 (decimal)
#                 #we get the pubkey from the spkac
#                 cert.set_pubkey(spki.get_pubkey())
#                 res = crypto.dump_certificate(crypto.FILETYPE_ASN1, cert)
#                 r = HttpResponse(mimetype="application/x-x509-user-cert")
#                 r.write(res)
#                 return r
#                 #XXX REFACTOR ##############################
# 
#             return render_to_response(
#                     'webid_provider/webid_identity_keygen.html',
#                     {'form': form,
#                     "MEDIA_URL": settings.MEDIA_URL,
#                     "STATIC_URL": settings.STATIC_URL,
#                     'messages': messages,
#                     }, context_instance=RequestContext(request))
#     else:
#         form = WebIdIdentityForm()  # An unbound form
# 
#     return render_to_response(
#             'webid_provider/webid_identity_keygen.html', {
#             #XXX TODO: add randomchars challenge...
#             'form': form,
#             "MEDIA_URL": settings.MEDIA_URL,
#             "STATIC_URL": settings.STATIC_URL,
#             'messages': messages,
#             }, context_instance=RequestContext(request))
# 
# 
# def webid_identity(request):
#     """
#     Create only http-WebID certificate
#     """
# 
#     #XXX TODO
#     #this is very similar to above
#     #function, but creates the cert as a pkcs12.
#     #XXX TODO CHANGE VIEW NAME!!! --> TO PKCS12_IDENTITY
#     #OR SOMETHING LIKE THAT...
# 
#     #REFACTOR!! ################################
# 
#     #Detect if using IExplorer (support needed?)
#     #and leave the .p12 as a fallback mechanism.
# 
#     errors = False
#     messages = []
# 
#     if request.method == 'POST':
#         form = WebIdIdentityForm(request.POST)
#         if form.is_valid():
#             if not errors:
#                 webid = str(form.cleaned_data['webid'])
#                 nick = str(form.cleaned_data['nick'])
#                 try:
#                     gen_httpwebid_selfsigned_cert_pemfile(webid, nick=nick)
#                     #XXX THIS IS THE SECOND MIX USE OF OPENSSL/M2CRYPTO
#                     path = pemfile_2_pkcs12file()
#                     #print "PKC12 path: " + path
#                 except Exception, e:
#                     message = "Error trying to generate client certificate: "\
#                     + str(e)
#                     messages.append(message)
#                     # can not continue
#                 else:
#                     fp = open(path)
#                     content = fp.read()
#                     fp.close()
#                     length = os.path.getsize(path)
#                     r = HttpResponse(mimetype="application/x-x509-user-cert")
#                     #handle = webid.split('/')[-1]
#                     # XXX ugly, but has to be something!
#                     r['Content-Disposition'] = 'attachment; filename=%s%s' % \
#                             (nick, "_cert.p12")
#                     r["Content-Length"] = length
#                     r["Accept-Ranges"] = "bytes"
#                     r.write(content)
#                     messages.append("created")
#                     return r
#             return render_to_response(
#                 'webid_provider/webid_identity.html', {
#                 'form': form,
#                 "MEDIA_URL": settings.MEDIA_URL,
#                 "STATIC_URL": settings.STATIC_URL,
#                 'messages': messages,
#             }, context_instance=RequestContext(request))
#     else:
#         form = WebIdIdentityForm()
# 
#     return render_to_response('webid_provider/webid_identity.html', {
#         'form': form,
#         "MEDIA_URL": settings.MEDIA_URL,
#         "STATIC_URL": settings.STATIC_URL,
#         'messages': messages,
#     }, context_instance=RequestContext(request))
# 
# 
# ###########################################
# #            SIGNALS                      #
# ###########################################
# 
# #We need to initialize a blank profile when a
# #WebIDUser is created (actually, when a User is
# #created, since it's a proxy model).
# #But this can cause problems if we do not have
# #enough mandatory fields filled up, or if
# #an equivalent signal is already in place.
# 
# #XXX only register if there's no other signal registered?
# #... that is subject to order issues.
# #XXX we can control this also with a WEBIDPROVIDER_SKIP_PROFILE_INIT
# #or something similar.
# 
# SKIP_PROFILE_INIT = getattr(settings, "WEBIDPROVIDER_SKIP_PROFILE_INIT", False)
# PROF_INIT_CB_KEY = "WEBIDPROVIDER_PROFILE_INIT_CALLBACK"
# 
# if not SKIP_PROFILE_INIT:
#     @receiver(post_save, sender=User)
#     def init_blank_profile_for_new_user(sender, **kwargs):
#         """
#         initializes a blank profile for webiduser
#         in the moment of its creation.
#         """
#         if kwargs.get('created', None):
#             user = kwargs.get('instance', None)
#             logger.warning('creating blank profile for user')
#             logger.warning('kwargs=%s' % kwargs)
# 
#             PROFILE_INIT_CB = getattr(settings,
#                     PROF_INIT_CB_KEY,
#                     None)
#             if PROFILE_INIT_CB:
#                 fun_split = PROFILE_INIT_CB.split('.')
# 
#                 if len(fun_split) == 3:
#                     app, module, fun_name = fun_split
#                     fun = getattr(
#                             getattr(__import__(app),
#                                 module),
#                             fun_name)
# 
#                 if len(fun_split) == 2:
#                     module, fun_name = fun_split
#                     fun = getattr(__import__(module),
#                             fun_name)
# 
#                 else:
#                     logger.warning('%s expected to be in the form \
# "app.module.function or module.function"')
# 
#                 if not callable(fun):
#                     raise ImproperlyConfigured(
#                         "A function is expected in \
# %s" % PROF_INIT_CB_KEY)
#                 try:
#                     fun(user=user)
#                     return
#                 except:
#                     logger.error('Error while calling \
# %s' % PROF_INIT_CB_KEY)
#                     raise
# 
#             webiduser = WebIDUser.objects.get(id=user.id)
# 
#             profile_model = settings.AUTH_PROFILE_MODULE
#             app_split = profile_model.split('.')
#             if len(app_split) == 2:
#                 app_label, mod_label = app_split
#             else:
#                 app_label, mod_label = app_split[-2:]
#             pklss = models.get_model(app_label, mod_label)
# 
#             try:
#                 pklss.objects.create(user=webiduser)
#             except IntegrityError:
#                 logger.error('Could not save profile object for user %s in \
# django_webid.provider signal' % webiduser)
#                 raise ImproperlyConfigured("Error when initializing blank \
# profile. Use WEBIDPROVIDER_SKIP_PROFILE_INIT if needed, or pass a callback.")
